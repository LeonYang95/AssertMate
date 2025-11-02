import sys

sys.path.extend(['.', '..'])
import os
from dotmap import DotMap
import json
import random
from tqdm import tqdm
from loguru import logger
from collections import Counter
from agents.Generator_Impls import NaiveGenerator, RAGGenerator, FourStepCoTGenerator
from agents.base.llm import DeepSeek
from utils.multi_processing_cache import load_cache, dump_cache
from utils.java_parsers import parse_variables
from data.base.dataset_factory import dataset_factory
import yaml
import multiprocessing
import pickle

random.seed(888)

code_base = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
with open(os.path.join(code_base, 'config/basic_config.yaml'), 'r') as reader:
    config = DotMap(yaml.load(reader, Loader=yaml.FullLoader))
model = DeepSeek(config)

# if debugging mode.
debug = True


def discussion(dual_groups, cache, pid, output_base):
    global debug
    members = [
        NaiveGenerator(model),
        RAGGenerator(model),
        FourStepCoTGenerator(model)
    ]

    if debug:
        dual_groups = dual_groups[:10]
    first_round_speak_up(
        dual_groups=dual_groups,
        members=members,
        cache=cache,
        output_base=output_base,
        pid=pid
    )


def first_round_speak_up(dual_groups, members, cache, output_base, pid) -> dict:
    # try:
    logger.info(f'PID {pid} has {len(dual_groups)} instance to process.')
    responses = {}
    for member in members:
        member_id = member.__class__.__name__
        responses[member_id] = {}
        writer = open(
            os.path.join(
                output_base, f'first_round_speak_up-{member_id}-{pid}-results.jsonl'), 'w',
            encoding='utf-8')
        for retrieved_group, target_group in tqdm(dual_groups,
                                                  desc=f'PID-{pid}: First round {member_id} is speaking up'):
            record_instance = {
                'member': member_id
            }
            instance, expected_value, raw_assertion, processed_assertion = target_group
            focal_method = instance.focal_method
            test_case = instance.test_case
            test_prefix = instance.test_prefix
            # local_variables = parse_variables(test_case)
            record_instance['id'] = instance.id
            record_instance['focal_method'] = focal_method
            record_instance['test_case'] = test_case
            record_instance['test_prefix'] = test_prefix
            record_instance['retrieved_focal_method'] = ''
            record_instance['retrieved_test_case'] = ''
            record_instance['expected_value'] = expected_value
            expected_value_type = 'boolean' if expected_value in [
                'assertTrue', 'assertFalse'] else None
            if retrieved_group is not None:
                # retrieved_instance, retrieved_expected_value, retrieved_raw_assertion, retrieved_processed_assertion = retrieved_group
                retrieved_instance, _, _, _ = retrieved_group
                retrieved_focal_method = retrieved_instance.focal_method
                retrieved_test_case = retrieved_instance.test_case
                # retrieved_test_prefix = retrieved_test_case.replace(retrieved_raw_assertion,
                #                                                     retrieved_processed_assertion)
                record_instance['retrieved_focal_method'] = retrieved_focal_method
                record_instance['retrieved_test_case'] = retrieved_test_case
            else:
                retrieved_focal_method = None
                # retrieved_test_prefix = None
                # retrieved_expected_value = None
                retrieved_test_case = None

            # focal_class_fields = [f.original_string for f in instance.focal_class_fields]
            # focal_class_methods = [m.full_signature for m in instance.focal_class_methods if
            #                        'public' in m.full_signature]
            # test_class_fields = [f.original_string for f in instance.test_class.fields]
            focal_class_fields = [f for f in instance.focal_class_fields]
            focal_class_methods = [m for m in instance.focal_class_methods if
                                   'public' in m]
            test_class_fields = [f for f in instance.test_class_fields]
            if expected_value in ['assertTrue', 'assertFalse']:
                response = member.generate_assertBoolean(
                    focal_method_name=instance.focal_method_name,
                    focal_method=focal_method,
                    focal_class_fields=focal_class_fields,
                    focal_class_methods=focal_class_methods,
                    test_class_fields=test_class_fields,
                    test_prefix=test_prefix,
                    retrieved_test_case=retrieved_test_case,
                    retrieved_focal_method=retrieved_focal_method,
                    cot_cache=cache,
                    expected_value_type=expected_value_type,
                    actual_value=instance.actual_value,
                    prefix=False
                )
            elif expected_value in ['assertNull', 'assertNotNull']:
                response = member.generate_assertNullValue(
                    focal_method_name=instance.focal_method_name,
                    focal_method=focal_method,
                    focal_class_fields=focal_class_fields,
                    focal_class_methods=focal_class_methods,
                    test_class_fields=test_class_fields,
                    test_prefix=test_prefix,
                    retrieved_test_case=retrieved_test_case,
                    retrieved_focal_method=retrieved_focal_method,
                    cot_cache=cache,
                    expected_value_type=expected_value_type,
                    actual_value=instance.actual_value,
                    prefix=False
                )
            else:
                response = member.generate_assertEquals(
                    focal_method_name=instance.focal_method_name,
                    focal_method=focal_method,
                    focal_class_fields=focal_class_fields,
                    focal_class_methods=focal_class_methods,
                    test_class_fields=test_class_fields,
                    # test_class_methods = test_class_methods,
                    test_prefix=test_prefix,
                    retrieved_test_case=retrieved_test_case,
                    retrieved_focal_method=retrieved_focal_method,
                    # retrieved_test_prefix=retrieved_test_prefix,
                    # retrieved_ground_truth=retrieved_expected_value,
                    cot_cache=cache,
                    expected_value_type=expected_value_type,
                    actual_value=instance.actual_value,
                    prefix=False
                )
            record_instance['history'] = member.history

            writer.write(json.dumps(record_instance,
                                    ensure_ascii=False) + '\n')
            responses[member_id][instance.id] = pickle.loads(
                pickle.dumps(member.history))
        writer.close()
    return responses


def record_results(num_process: int):
    # First Round

    first_round_naive_result = os.path.join(
        output_base, 'first_round_speak_up-NaiveGenerator-results.jsonl')
    first_round_naive_result_formatter = os.path.join(output_base,
                                                      'first_round_speak_up-NaiveGenerator-{}-results.jsonl')
    _merge_multiprocessing_record_files(num_process, first_round_naive_result,
                                        first_round_naive_result_formatter)

    first_round_rag_result = os.path.join(
        output_base, 'first_round_speak_up-RAGGenerator-results.jsonl')
    first_round_rag_result_formatter = os.path.join(output_base,
                                                    'first_round_speak_up-RAGGenerator-{}-results.jsonl')
    _merge_multiprocessing_record_files(num_process, first_round_rag_result,
                                        first_round_rag_result_formatter)

    first_round_rag_result = os.path.join(output_base,
                                          'first_round_speak_up-FourStepCoTGenerator-results.jsonl')
    first_round_rag_result_formatter = os.path.join(output_base,
                                                    'first_round_speak_up-FourStepCoTGenerator-{}-results.jsonl')
    _merge_multiprocessing_record_files(num_process, first_round_rag_result,
                                        first_round_rag_result_formatter)

    pass


def _merge_multiprocessing_record_files(num_process: int, output_file: str, input_filename_formatter: str):
    with open(output_file, 'w', encoding='utf-8') as writer:
        for pid in range(num_process):
            input_file = input_filename_formatter.format(pid)
            if os.path.exists(input_file):
                with open(input_file, 'r', encoding='utf-8') as reader:
                    for line in reader.readlines():
                        writer.write(line)
                os.remove(input_file)
    pass


if __name__ == '__main__':
    # For future cmd params
    # dataset = sys.args[1]
    # dataset = 'methods2test'
    # dataset = 'defects4j'
    dataset = 'defects4j'

    ds = dataset_factory(config, dataset)
    data = ds.load_retrieval_data(top_k=1)
    cache = load_cache(code_base)

    # randomly sample data for inferencing
    random.shuffle(data)

    output_base = os.path.join(code_base, 'results/discussions/r1_distill_wo_prefill')
    if not os.path.exists(output_base):
        os.makedirs(output_base)
    num_process = 10
    num_per_chunk = len(data) // num_process
    num_per_chunk += 1
    chunks = [data[i * num_per_chunk: (i + 1) * num_per_chunk]
              for i in range(num_process)]
    assert len(chunks) == num_process

    if debug:
        discussion(chunks[4], cache, 0, output_base)
        dump_cache(code_base, dict(cache.cot_thoughts))
        record_results(1)
        pass
    else:
        jobs = []
        for pid, chunk in enumerate(chunks):
            p = multiprocessing.Process(
                target=discussion, args=(chunk, cache, pid, output_base))
            jobs.append(p)
            p.start()

        for job in jobs:
            job.join()
        dump_cache(code_base, dict(cache.cot_thoughts))
        record_results(num_process)

    pass
