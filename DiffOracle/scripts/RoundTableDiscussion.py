import sys

sys.path.extend(['.', '..'])
import os
import yaml, multiprocessing, pickle
from dotmap import DotMap
import json
import random
from tqdm import tqdm
from loguru import logger

from agents.Generator_Impls import NaiveGenerator, AutoCoTGenerator
from agents.Judge import Judge
from agents.base.llm import DeepSeek
from utils.multi_processing_cache import load_cache, dump_cache
from data.base.dataset_factory import dataset_factory

random.seed(666)

code_base = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
with open(os.path.join(code_base, 'config/basic_config.yaml'), 'r') as reader:
    config = DotMap(yaml.load(reader, Loader=yaml.FullLoader))
model = DeepSeek(config)

# if debugging mode.
debug = True


def discussion(dual_groups, cache, pid, output_base):
    global debug
    # members = [NaiveGenerator(model), CoTGenerator(model), RAGGenerator(model), AutoCoTGenerator(model)]
    # members = [FIMGenerator(model)]
    members = [NaiveGenerator(model), AutoCoTGenerator(model)]
    judge = Judge(model)

    # TODO: Remove this when running large-scale evaluation.
    dual_groups = dual_groups[:10]

    generator_responses = first_round_speak_up(
        dual_groups=dual_groups,
        members=members,
        cache=cache,
        output_base=output_base,
        pid=pid)

    judge_responses = judge_consistency(dual_groups, judge, generator_responses, output_base, pid)

    assert len(dual_groups) == len(judge_responses)

    generator_responses_refine = {}
    dual_groups_refine = []
    judge_responses_refine = {}
    for dual_group in dual_groups:
        _, target_group = dual_group
        instance, _, _, _ = target_group
        verdict = judge_responses[instance.id][0]
        if '**YES**' in verdict:
            continue
        else:
            dual_groups_refine.append(dual_group)
            judge_responses_refine[instance.id] = judge_responses[instance.id]
            for member, history in generator_responses.items():
                if member not in generator_responses_refine:
                    generator_responses_refine[member] = {}
                generator_responses_refine[member][instance.id] = history[instance.id]
    if len(dual_groups_refine) != 0:
        assert len(dual_groups_refine) == len(judge_responses_refine) == len(generator_responses_refine['CoTGenerator'])
        logger.info(f'{len(dual_groups_refine)} need to be refined.')
        refined_responses = second_round_refine(dual_groups_refine, judge_responses_refine, members,
                                                generator_responses_refine, output_base, pid)
        judge_final_decision(dual_groups_refine, judge, refined_responses, pid, output_base)
    pass


def first_round_speak_up(dual_groups, members, cache, output_base, pid) -> dict:
    member_id = ''
    try:
        responses = {}
        for member in members:
            member_id = member.__class__.__name__
            responses[member_id] = {}
            writer = open(
                os.path.join(output_base, f'first_round_speak_up-{member_id}-{pid}-results.jsonl'), 'w',
                encoding='utf-8')
            for retrieved_group, target_group in tqdm(dual_groups,
                                                      desc=f'First round {member_id} is speaking up'):
                record_instance = {
                    'member': member_id
                }
                instance, expected_value, raw_assertion, processed_assertion = target_group
                focal_method = instance.focal_method.body
                test_case = instance.test_case.body
                test_prefix = test_case.replace(raw_assertion, processed_assertion, 1)

                record_instance['id'] = instance.id
                record_instance['focal_method'] = focal_method
                record_instance['test_case'] = test_case
                record_instance['test_prefix'] = test_prefix
                record_instance['retrieved_focal_method'] = ''
                record_instance['retrieved_test_case'] = ''
                record_instance['expected_value'] = expected_value

                if retrieved_group is not None:
                    retrieved_instance, retrieved_expected_value, retrieved_raw_assertion, retrieved_processed_assertion = retrieved_group
                    retrieved_focal_method = retrieved_instance.focal_method.body
                    retrieved_test_case = retrieved_instance.test_case.body
                    retrieved_test_prefix = retrieved_test_case.replace(retrieved_raw_assertion,
                                                                        retrieved_processed_assertion)
                    record_instance['retrieved_focal_method'] = retrieved_focal_method
                    record_instance['retrieved_test_case'] = retrieved_test_case
                else:
                    retrieved_focal_method = None
                    retrieved_test_prefix = None
                    retrieved_expected_value = None

                focal_class_fields = [f.original_string for f in instance.focal_class.fields]
                focal_class_methods = [m.full_signature for m in instance.focal_class.methods if
                                       'public' in m.full_signature]
                test_class_fields = [f.original_string for f in instance.test_class.fields]

                response = member.generate_assertEquals(
                    focal_method_name=instance.focal_method.identifier,
                    focal_method=focal_method,
                    focal_class_fields=focal_class_fields,
                    focal_class_methods=focal_class_methods,
                    test_class_fields=test_class_fields,
                    # test_class_methods = test_class_methods,
                    test_prefix=test_prefix,
                    retrieved_focal_method=retrieved_focal_method,
                    retrieved_test_prefix=retrieved_test_prefix,
                    retrieved_ground_truth=retrieved_expected_value,
                    cot_cache=cache
                )
                record_instance['history'] = member.history
                writer.write(json.dumps(record_instance, ensure_ascii=False) + '\n')
                responses[member_id][instance.id] = member.history
            writer.close()
        return responses
    except:
        # In case there are unexpected errors, we need to dump the cache.
        dump_cache(code_base, dict(cache.cot_thoughts))


def judge_consistency(dual_groups, judge: Judge, responses: dict, output_base, pid) -> dict:
    judge_result = {}
    writer = open(os.path.join(output_base, f'first_round_judge-{pid}-results.jsonl'), 'w', encoding='utf-8')
    for retrieved_group, target_group in tqdm(dual_groups, desc='First round judging'):
        instance, expected_value, raw_assertion, processed_assertion = target_group
        focal_method = instance.focal_method.body
        test_case = instance.test_case.body
        test_prefix = test_case.replace(raw_assertion, processed_assertion, 1)
        final_responses = {}
        for member, history in responses.items():
            final_responses[member] = history[instance.id][-1].get('content')
        verdict = judge.make_decision(focal_method, test_prefix, final_responses)
        explain = judge.explain_decision(focal_method, test_prefix, final_responses, verdict, processed_assertion)
        judge_result[instance.id] = [verdict, explain]
        record_instance = {
            'id': instance.id,
            'focal_method': focal_method,
            'test_case': test_case,
            'test_prefix': test_prefix,
            'expected_value': expected_value,
            'first_round_speak_ups': final_responses,
            'first_round_verdict': verdict,
            'verdict_explain': explain,
        }
        writer.write(json.dumps(record_instance, ensure_ascii=False) + '\n')
    writer.close()
    return judge_result


def second_round_refine(dual_groups, judge_responses, members, member_previous_responses, output_base, pid) -> dict:
    responses = {}
    for member in members:
        member_id = member.__class__.__name__
        responses[member_id] = {}
        history = member_previous_responses[member_id]
        writer = open(
            os.path.join(output_base, f'second_round_speak_up-{member.__class__.__name__}-{pid}-results.jsonl'), 'w',
            encoding='utf-8')
        for retrieved_group, target_group in tqdm(dual_groups,
                                                  desc=f'Second round {member.__class__.__name__} is speaking up'):
            record_instance = {
                'member': member_id
            }
            instance, expected_value, raw_assertion, processed_assertion = target_group
            judge_response = judge_responses[instance.id][1]
            record_instance['id'] = instance.id
            member.clear_history()
            member.update_history(history[instance.id])
            member.refine(
                judge_response=judge_response
            )
            record_instance['history'] = member.history
            record_instance['expected_value'] = expected_value
            writer.write(json.dumps(record_instance, ensure_ascii=False) + '\n')
            responses[member_id][instance.id] = pickle.loads(pickle.dumps(member.history))
        writer.close()
    return responses


def judge_final_decision(dual_groups, judge, refined_responses: dict, pid, output_base) -> dict:
    judge_result = {}
    writer = open(os.path.join(output_base, f'final_judge-{pid}-results.jsonl'), 'w', encoding='utf-8')
    error_writer = open(os.path.join(output_base, f'error-{pid}.jsonl'), 'w', encoding='utf-8')
    for retrieved_group, target_group in tqdm(dual_groups, desc='Final round judging'):
        instance, expected_value, raw_assertion, processed_assertion = target_group
        focal_method = instance.focal_method.body
        test_case = instance.test_case.body
        test_prefix = test_case.replace(raw_assertion, processed_assertion, 1)
        final_responses = {}
        for member, history in refined_responses.items():
            final_responses[member] = history[instance.id][-1].get('content')
        try:
            verdict = judge.final_decision(focal_method, test_prefix, final_responses)
            judge_result[instance.id] = verdict
            record_instance = {
                'id': instance.id,
                'focal_method': focal_method,
                'test_case': test_case,
                'test_prefix': test_prefix,
                'expected_value': expected_value,
                'second_round_speak_ups': final_responses,
                'final_verdict': verdict
            }
            writer.write(json.dumps(record_instance, ensure_ascii=False) + '\n')
        except Exception as e:
            error_writer.write(
                json.dumps({
                    'id': instance.id,
                    'err_msg': str(e),
                    'history': judge.history
                })
            )
        finally:
            continue

    writer.close()
    error_writer.close()
    return judge_result


def record_results(num_process: int):
    # Final Judge
    final_judge_result = os.path.join(output_base, 'final_judge-results.jsonl')
    final_judge_result_formatter = os.path.join(output_base, 'final_judge-{}-results.jsonl')
    _merge_multiprocessing_record_files(num_process, final_judge_result, final_judge_result_formatter)

    # Second Round
    second_round_cot_result = os.path.join(output_base, 'second_round_speak_up-CoTGenerator-results.jsonl')
    second_round_cot_result_formatter = os.path.join(output_base,
                                                     'second_round_speak_up-CoTGenerator-{}-results.jsonl')
    _merge_multiprocessing_record_files(num_process, second_round_cot_result, second_round_cot_result_formatter)

    second_round_cot_result = os.path.join(output_base, 'second_round_speak_up-AutoCoTGenerator-results.jsonl')
    second_round_cot_result_formatter = os.path.join(output_base,
                                                     'second_round_speak_up-AutoCoTGenerator-{}-results.jsonl')
    _merge_multiprocessing_record_files(num_process, second_round_cot_result, second_round_cot_result_formatter)

    second_round_naive_result = os.path.join(output_base, 'second_round_speak_up-NaiveGenerator-results.jsonl')
    second_round_naive_result_formatter = os.path.join(output_base,
                                                       'second_round_speak_up-NaiveGenerator-{}-results.jsonl')
    _merge_multiprocessing_record_files(num_process, second_round_naive_result,
                                        second_round_naive_result_formatter)

    second_round_rag_result = os.path.join(output_base, 'second_round_speak_up-RAGGenerator-results.jsonl')
    second_round_rag_result_formatter = os.path.join(output_base,
                                                     'second_round_speak_up-RAGGenerator-{}-results.jsonl')
    _merge_multiprocessing_record_files(num_process, second_round_rag_result,
                                        second_round_rag_result_formatter)

    # First Round Judge
    final_judge_result = os.path.join(output_base, 'first_round_judge-results.jsonl')
    final_judge_result_formatter = os.path.join(output_base, 'first_round_judge-{}-results.jsonl')
    _merge_multiprocessing_record_files(num_process, final_judge_result, final_judge_result_formatter)

    # First Round Speak Ups
    first_round_cot_result = os.path.join(output_base, 'first_round_speak_up-CoTGenerator-results.jsonl')
    first_round_cot_result_formatter = os.path.join(output_base,
                                                    'first_round_speak_up-CoTGenerator-{}-results.jsonl')
    _merge_multiprocessing_record_files(num_process, first_round_cot_result, first_round_cot_result_formatter)

    first_round_cot_result = os.path.join(output_base, 'first_round_speak_up-AutoCoTGenerator-results.jsonl')
    first_round_cot_result_formatter = os.path.join(output_base,
                                                    'first_round_speak_up-AutoCoTGenerator-{}-results.jsonl')
    _merge_multiprocessing_record_files(num_process, first_round_cot_result, first_round_cot_result_formatter)

    first_round_naive_result = os.path.join(output_base, 'first_round_speak_up-NaiveGenerator-results.jsonl')
    first_round_naive_result_formatter = os.path.join(output_base,
                                                      'first_round_speak_up-NaiveGenerator-{}-results.jsonl')
    _merge_multiprocessing_record_files(num_process, first_round_naive_result,
                                        first_round_naive_result_formatter)

    first_round_rag_result = os.path.join(output_base, 'first_round_speak_up-RAGGenerator-results.jsonl')
    first_round_rag_result_formatter = os.path.join(output_base,
                                                    'first_round_speak_up-RAGGenerator-{}-results.jsonl')
    _merge_multiprocessing_record_files(num_process, first_round_rag_result,
                                        first_round_rag_result_formatter)

    # Errors
    error_result = os.path.join(output_base, 'error-results.jsonl')
    error_result_formatter = os.path.join(output_base, 'error-{}.jsonl')
    _merge_multiprocessing_record_files(num_process, error_result, error_result_formatter)

    pass


def _merge_multiprocessing_record_files(num_process: int, output_file: str, input_filename_formatter: str):
    with open(output_file, 'w', encoding='utf-8') as writer:
        for pid in range(num_process):
            input_file = input_filename_formatter.format(pid)
            if os.path.exists(input_file):
                with open(input_file, 'r', encoding='utf-8') as reader:
                    for line in reader:
                        writer.write(line)
                os.remove(input_file)
    pass


if __name__ == '__main__':
    # For future cmd params
    # dataset = sys.args[1]
    dataset = 'methods2test'

    ds = dataset_factory(config, dataset)
    data = ds.load_retrieval_data(top_k=1)
    cache = load_cache(code_base)

    # randomly sample data for inferencing
    random.shuffle(data)

    output_base = os.path.join(code_base, 'results')
    if not os.path.exists(output_base): os.makedirs(output_base)
    num_process = 10
    num_per_chunk = len(data) // num_process
    num_per_chunk += 1
    chunks = [data[i * num_per_chunk: (i + 1) * num_per_chunk] for i in range(num_process)]
    assert len(chunks) == num_process

    if debug:
        discussion(chunks[4], cache, 0, output_base)
        dump_cache(code_base, dict(cache.cot_thoughts))
        record_results(1)
        pass
    else:
        jobs = []
        for pid, chunk in enumerate(chunks):
            p = multiprocessing.Process(target=discussion, args=(chunk, cache, pid, output_base))
            jobs.append(p)
            p.start()

        for job in jobs:
            job.join()
        dump_cache(code_base, dict(cache.cot_thoughts))
        record_results(num_process)

    pass
