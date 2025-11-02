import sys

sys.path.extend(['.', '..'])
import os
import yaml, multiprocessing, pickle
from dotmap import DotMap
import json
import random
from tqdm import tqdm
from loguru import logger
from collections import Counter

from agents.Generator_Impls import NaiveGenerator, AutoCoTGenerator, CoTGenerator, RAGGenerator, FourStepCoTGenerator
from agents.base.llm import DeepSeek
from utils.multi_processing_cache import load_cache, dump_cache
from utils.java_parsers import parse_variables
from data.base.dataset_factory import dataset_factory

random.seed(888)

code_base = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
with open(os.path.join(code_base, 'config/basic_config.yaml'), 'r') as reader:
    config = DotMap(yaml.load(reader, Loader=yaml.FullLoader))
model = DeepSeek(config)

# if debugging mode.
debug = True


def discussion(dual_groups, cache, pid, output_base):
    global debug
    members = [NaiveGenerator(model), CoTGenerator(model), RAGGenerator(model), AutoCoTGenerator(model),
               FourStepCoTGenerator(model)]
    # members = [FourStepCoTGenerator(model)]


    final_results = {}
    first_round_responses = first_round_speak_up(
        dual_groups=dual_groups,
        members=members,
        cache=cache,
        output_base=output_base,
        pid=pid)

    refined_responses = None
    response_histories = first_round_responses
    maximum_retries = 3
    last_round_groups_to_refine = dual_groups

    while maximum_retries > 0:
        # 判断是否达到了一致, 达到一致为止，或者达到最大迭代次数为止。
        dual_groups_to_refine = []
        maximum_retries -= 1
        current_round_responses = {}
        for dual_group in last_round_groups_to_refine:
            _, target_group = dual_group
            instance, expected_value, _, processed_assertion = target_group

            # 收集上一轮的输出结果
            response_set = set()
            current_round_responses[instance.id] = {}
            responses_for_record = {}
            for member in members:
                member_id = member.__class__.__name__
                response = response_histories[member_id][instance.id][-1].get('content', '').strip()
                responses_for_record[member_id] = pickle.loads(pickle.dumps(response_histories[member_id][instance.id]))
                response_set.add(response)
                current_round_responses[instance.id][member_id] = response

            # 判断是否达成了一致
            if len(response_set) == 1:
                # 如果一致，那么记录这个一致的结果
                final_results[instance.id] = {
                    'focal_method': pickle.loads(pickle.dumps(instance.focal_method)),
                    'test_case': pickle.loads(pickle.dumps(instance.test_case)),
                    'expected_value': pickle.loads(pickle.dumps(expected_value)),
                    'processed_assertion': pickle.loads(pickle.dumps(processed_assertion)),
                    'response': response_set.pop(),
                    'complete_responses': pickle.loads(pickle.dumps(responses_for_record)),
                }
                response_set.clear()
                pass
            else:
                # 如果不一致，那么记录这个不一致的case，后续进行refine。
                dual_groups_to_refine.append(dual_group)

        if len(dual_groups_to_refine) != 0:
            logger.info(f'{len(dual_groups_to_refine)} need to be refined. {maximum_retries} rounds remains.')
            refined_responses = refine(dual_groups_to_refine, members, response_histories, current_round_responses,
                                       output_base, pid)
            response_histories = pickle.loads(pickle.dumps(refined_responses))
            last_round_groups_to_refine = pickle.loads(pickle.dumps(dual_groups_to_refine))
            dual_groups_to_refine.clear()
            continue
        else:
            refined_responses = None
            logger.info(f'All set ({pid}). No need to refine.')
            break

    if refined_responses and len(last_round_groups_to_refine) != 0:
        for dual_group in last_round_groups_to_refine:
            voting = Counter()
            _, target_group = dual_group
            instance, expected_value, _, processed_assertion = target_group
            responses_for_record = {}
            for member in members:
                member_id = member.__class__.__name__
                response = refined_responses[member_id][instance.id][-1].get('content', '').strip()
                responses_for_record[member_id] = pickle.loads(pickle.dumps(refined_responses[member_id][instance.id]))
                voting[response] += 1

            final_answer = voting.most_common(1)[0][0]
            final_results[instance.id] = {
                'focal_method': pickle.loads(pickle.dumps(instance.focal_method)),
                'test_case': pickle.loads(pickle.dumps(instance.test_case)),
                'expected_value': pickle.loads(pickle.dumps(expected_value)),
                'processed_assertion': pickle.loads(pickle.dumps(processed_assertion)),
                'response': pickle.loads(pickle.dumps(final_answer)),
                'complete_responses': pickle.loads(pickle.dumps(responses_for_record)),
            }
    with open(os.path.join(code_base, f'results/debug_no_judge-{pid}-results.jsonl'), 'w', encoding='utf-8') as writer:
        for instance_id, record in final_results.items():
            writer.write(json.dumps({'id': instance_id, 'record': record}, ensure_ascii=False) + '\n')
    pass


def first_round_speak_up(dual_groups, members, cache, output_base, pid) -> dict:
    try:
        responses = {}
        for member in members:
            member_id = member.__class__.__name__
            responses[member_id] = {}
            writer = open(
                os.path.join(output_base, f'debug_no_judge-first_round_speak_up-{member_id}-{pid}-results.jsonl'), 'w',
                encoding='utf-8')
            for retrieved_group, target_group in tqdm(dual_groups,
                                                      desc=f'PID-{pid}: First round {member_id} is speaking up'):
                record_instance = {
                    'member': member_id
                }
                instance, expected_value, raw_assertion, processed_assertion = target_group
                focal_method = instance.focal_method
                test_case = instance.test_case
                test_prefix = test_case.replace(raw_assertion, processed_assertion, 1)
                # local_variables = parse_variables(test_case)
                record_instance['id'] = instance.id
                record_instance['focal_method'] = focal_method
                record_instance['test_case'] = test_case
                record_instance['test_prefix'] = test_prefix
                record_instance['retrieved_focal_method'] = ''
                record_instance['retrieved_test_case'] = ''
                record_instance['expected_value'] = expected_value
                expected_value_type = 'boolean' if expected_value in ['true', 'false'] else None
                if retrieved_group is not None:
                    retrieved_instance, retrieved_expected_value, retrieved_raw_assertion, retrieved_processed_assertion = retrieved_group
                    retrieved_focal_method = retrieved_instance.focal_method
                    retrieved_test_case = retrieved_instance.test_case
                    retrieved_test_prefix = retrieved_test_case.replace(retrieved_raw_assertion,
                                                                        retrieved_processed_assertion)
                    record_instance['retrieved_focal_method'] = retrieved_focal_method
                    record_instance['retrieved_test_case'] = retrieved_test_case
                else:
                    retrieved_focal_method = None
                    retrieved_test_prefix = None
                    retrieved_expected_value = None

                # focal_class_fields = [f.original_string for f in instance.focal_class_fields]
                # focal_class_methods = [m.full_signature for m in instance.focal_class_methods if
                #                        'public' in m.full_signature]
                # test_class_fields = [f.original_string for f in instance.test_class.fields]
                focal_class_fields = [f for f in instance.focal_class_fields]
                focal_class_methods = [m for m in instance.focal_class_methods if
                                       'public' in m]
                test_class_fields = [f for f in instance.test_class_fields]

                response = member.generate_assertEquals(
                    focal_method_name=instance.focal_method_name,
                    focal_method=focal_method,
                    focal_class_fields=focal_class_fields,
                    focal_class_methods=focal_class_methods,
                    test_class_fields=test_class_fields,
                    # test_class_methods = test_class_methods,
                    test_prefix=test_prefix,
                    retrieved_focal_method=retrieved_focal_method,
                    retrieved_test_prefix=retrieved_test_prefix,
                    retrieved_ground_truth=retrieved_expected_value,
                    cot_cache=cache,
                    expected_value_type=expected_value_type,
                    prefix=False
                )
                record_instance['history'] = member.history
                writer.write(json.dumps(record_instance, ensure_ascii=False) + '\n')
                responses[member_id][instance.id] = pickle.loads(pickle.dumps(member.history))
            writer.close()
        return responses
    except:
        # In case there are unexpected errors, we need to dump the cache.
        dump_cache(code_base, dict(cache.cot_thoughts))


def refine(dual_groups, members, member_history, last_responses, output_base, pid) -> dict:
    responses = {}
    for member in members:
        member_id = member.__class__.__name__
        responses[member_id] = {}
        history = member_history[member_id]
        writer = open(
            os.path.join(output_base, f'debug_no_judge_refined_speak_up-{member.__class__.__name__}-{pid}-results.jsonl'),
            'w',
            encoding='utf-8')
        for retrieved_group, target_group in tqdm(dual_groups,
                                                  desc=f'{member.__class__.__name__} is refining'):
            record_instance = {
                'member': member_id
            }
            instance, expected_value, raw_assertion, processed_assertion = target_group
            prev_responses = last_responses[instance.id]
            record_instance['id'] = instance.id
            local_variables = parse_variables(instance.test_case)
            member.clear_history()
            member.update_history(history[instance.id])
            member.refine_no_judge(
                prev_responses=prev_responses,
                test_case_local_variables=local_variables,

            )
            record_instance['history'] = member.history
            record_instance['expected_value'] = expected_value
            writer.write(json.dumps(record_instance, ensure_ascii=False) + '\n')
            responses[member_id][instance.id] = pickle.loads(pickle.dumps(member.history))
        writer.close()
    return responses

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

    debug_instances = [
        '81368488_47',
        '29603649_23',
        '25359676_43'
    ]
    debug_data = []
    for dual_group in data:
        _, target_group = dual_group
        instance  = target_group[0]
        if instance.id not in debug_instances:
            continue
        else:
            debug_data.append(dual_group)

    data = debug_data
    output_base = os.path.join(code_base, 'results')
    if not os.path.exists(output_base): os.makedirs(output_base)

    if debug:
        discussion(data, cache, 0, output_base)
        dump_cache(code_base, dict(cache.cot_thoughts))
        # record_results(1)

    pass
