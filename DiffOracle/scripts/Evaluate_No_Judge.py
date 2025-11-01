import sys

sys.path.extend(['.', '..'])
import os, json, yaml
from agents.Generator_Impls import *
from loguru import logger
from collections import Counter
from dotmap import DotMap


def load_jsonl_file_as_dict(file_path) -> dict:
    if not os.path.exists(file_path):
        logger.error(f'Target JSONL file {file_path} does not exist.')
        return {}
    else:
        res = {}
        with open(file_path, 'r', encoding='utf-8') as reader:
            for line in reader.readlines():
                line = line.strip()
                if line == '':
                    continue
                else:
                    d = json.loads(line)
                    res[d['id']] = d['record']
        return res


def load_first_round_jsonl_file_as_dict(file_path) -> dict:
    if not os.path.exists(file_path):
        logger.error(f'Target JSONL file {file_path} does not exist.')
        return {}
    else:
        res = {}
        with open(file_path, 'r', encoding='utf-8') as reader:
            for line in reader.readlines():
                line = line.strip()
                if line == '':
                    continue
                else:
                    d = json.loads(line)
                    res[d['id']] = pickle.loads(pickle.dumps(d))
        return res


code_base = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
res_dict = load_jsonl_file_as_dict(os.path.join(code_base, 'results/no_judge-results.jsonl'))
members = ['NaiveGenerator', 'CoTGenerator', 'RAGGenerator', 'AutoCoTGenerator',
           'FourStepCoTGenerator']
if __name__ == '__main__':
    total = 0
    in_source_total = 0
    in_source_correct = 0
    final_correct = 0
    at_least_one_correct = 0
    summary_by_generator = Counter()
    final_correct_set = set()
    for id, record in res_dict.items():
        total += 1
        expected_value = record['expected_value']
        final_response = record['response']
        input = record['complete_responses']['NaiveGenerator'][1]['content']
        in_source = False
        if expected_value in input:
            in_source = True
            in_source_total += 1
        if expected_value in final_response:
            if in_source:
                in_source_correct += 1
            final_correct += 1
            final_correct_set.add(id)
            continue
        else:
            if expected_value in ['true', 'false'] and all([ev not in final_response for ev in ['true', 'false']]):
                total -= 1
                logger.warning(f'Expected value not found in final response: {record["processed_assertion"]}')
                continue
            if record['complete_responses'] == '':
                continue

    upper_bound_members = ['NaiveGenerator', 'FourStepCoTGenerator', 'RAGGenerator']
    # upper_bound_members = members
    generation_result = {}
    correct_by_member = Counter()
    found_by_RAG = set()
    found_set = set()
    total=100
    for member in upper_bound_members:
        generation_result[member] = set()
        first_round_res = load_first_round_jsonl_file_as_dict(
            os.path.join(code_base, f'results/no_judge-first_round_speak_up-{member}-results.jsonl'))
        for id, record in first_round_res.items():
            expected_value = record['expected_value']
            final_response = record['history'][-1].get('content')
            if expected_value in final_response:
                generation_result[member].add(id)
                correct_by_member[member] += 1
                if member == 'RAGGenerator' and id not in found_set:
                    found_by_RAG.add(id)
                    pass
                found_set.add(id)
                continue

    # from data.base.dataset_factory import dataset_factory
    #
    # with open(os.path.join(code_base, 'config/basic_config.yaml'), 'r') as reader:
    #     config = DotMap(yaml.load(reader, Loader=yaml.FullLoader))
    # ds = dataset_factory(config, 'methods2test')
    # data = ds.load_retrieval_data(top_k=1)
    # has_retrieved_res = 0
    # for dual_groups in data:
    #     retrieved_group, target_group = dual_groups
    #     instance, expected_value, raw_assertion, processed_assertion = target_group
    #     if instance.id in found_by_RAG:
    #         if retrieved_group:
    #             has_retrieved_res += 1
    #         pass
    #     else:
    #         continue
    #
    print(len(found_by_RAG))
    # print(has_retrieved_res)
    print(found_by_RAG)
    # print(found_set - final_correct_set)
    # print('Final:', end=' ')
    # print(final_correct, total, final_correct / total)

    # print('Expected Value in f-t pairL:', end=' ')
    # print(in_source_correct, in_source_total, in_source_correct / in_source_total)

    print('Upper bound:', end=' ')
    print(len(found_set), total, len(found_set) / total)

    print('Summary by generator:')
    for generator, count in summary_by_generator.items():
        print(f'{generator}: {count}')

    print('Correct by member:')
    for member, count in correct_by_member.most_common():
        print(f'{member}:{count}')
    pass
