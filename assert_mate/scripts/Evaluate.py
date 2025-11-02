import sys

sys.path.extend(['.', '..'])
import os, json, pickle, re
from loguru import logger
from collections import Counter


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
                    res[d['id']] = d
        return res


code_base = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))

first_round_res = load_jsonl_file_as_dict(os.path.join(code_base, 'results/first_round_judge-results.jsonl'))
second_round_res = load_jsonl_file_as_dict(os.path.join(code_base, 'results/final_judge-results.jsonl'))


def rough_evaluation(first_round_res, second_round_res):
    total = 0
    correct = 0
    missed_ids = []
    for key, record in first_round_res.items():
        total += 1
        if '**YES**' in record['first_round_verdict']:
            if re.sub('\s+', '', record['expected_value']) in re.sub('\s+', '', record['verdict_explain']):
                correct += 1
            else:
                missed_ids.append(record['id'])
            pass
        else:
            if key in second_round_res:
                final_record = second_round_res[key]
                if re.sub('\s+', '', final_record['expected_value']) in re.sub('\s+', '',
                                                                               final_record['final_verdict']):
                    correct += 1
                else:
                    missed_ids.append(record['id'])
        pass
    print('DiffOracle:', end=' ')
    print(correct, total, correct / total)
    return missed_ids


def calculate_at_least_one_agent_correct(missed_ids):
    correct_count = Counter()
    still_missing = []
    correct_in_first_round = 0
    correct_in_second_round = 0
    record = {
        'CoTGenerator': {},
        'RAGGenerator': {},
        'NaiveGenerator': {},
        'AutoCoTGenerator':{}
    }
    for member, _ in record.items():
        file_name = os.path.join(code_base, f'results/first_round_speak_up-{member}-results.jsonl')
        first_round_res = load_jsonl_file_as_dict(file_name)
        file_name = os.path.join(code_base, f'results/second_round_speak_up-{member}-results.jsonl')
        second_round_res = load_jsonl_file_as_dict(file_name)
        record[member]['first'] = pickle.loads(pickle.dumps(first_round_res))
        record[member]['second'] = pickle.loads(pickle.dumps(second_round_res))

    for id in missed_ids:
        found = False
        for member, records in record.items():
            first_round_response = records['first'][id]['history'][-1].get('content')
            ground_truth = records['first'][id]['expected_value']
            if re.sub('\s+', '', ground_truth) in re.sub('\s+', '', first_round_response):
                found = True
                correct_count[member] += 1
            else:
                if id in records['second']:
                    second_round_response = records['second'][id]['history'][-1].get('content')
                    if re.sub('\s+', '', ground_truth) in re.sub('\s+', '', second_round_response):
                        found = True
                        correct_count[member] += 1
            pass
        if not found:
            still_missing.append(id)
        else:
            correct_in_first_round += 1

    print(correct_in_first_round)
    print(correct_count)
    print(len(still_missing))
    print(still_missing)

    pass


def baseline():
    total = 0
    correct = 0
    file_path = os.path.join(code_base, f'results/first_round_speak_up-NaiveGenerator-results.jsonl')
    res = load_jsonl_file_as_dict(file_path)
    for key, record in res.items():
        total += 1
        if re.sub('\s+', '', record['expected_value']) in re.sub('\s+', '', record['history'][-1]['content']):
            correct += 1
    print('Baseline:', end=' ')
    print(correct, total, correct / total)


def upper_bound():
    total = 0
    corrected = set()
    file_path = os.path.join(code_base, f'results/first_round_speak_up-NaiveGenerator-results.jsonl')
    res = load_jsonl_file_as_dict(file_path)
    for key, record in res.items():
        total += 1
        if re.sub('\s+', '', record['expected_value']) in re.sub('\s+', '', record['history'][-1]['content']):
            corrected.add(record['id'])

    file_path = os.path.join(code_base, f'results/first_round_speak_up-CoTGenerator-results.jsonl')
    res = load_jsonl_file_as_dict(file_path)
    for key, record in res.items():
        if key in corrected:
            continue
        if re.sub('\s+', '', record['expected_value']) in re.sub('\s+', '', record['history'][-1]['content']):
            corrected.add(record['id'])

    file_path = os.path.join(code_base, f'results/first_round_speak_up-RAGGenerator-results.jsonl')
    res = load_jsonl_file_as_dict(file_path)
    for key, record in res.items():
        if key in corrected:
            continue
        if re.sub('\s+', '', record['expected_value']) in re.sub('\s+', '', record['history'][-1]['content']):
            corrected.add(record['id'])


    file_path = os.path.join(code_base, f'results/first_round_speak_up-AutoCoTGenerator-results.jsonl')
    res = load_jsonl_file_as_dict(file_path)
    for key, record in res.items():
        if key in corrected:
            continue
        if re.sub('\s+', '', record['expected_value']) in re.sub('\s+', '', record['history'][-1]['content']):
            corrected.add(record['id'])

    print('UpperBound:', end=' ')
    print(len(corrected), total, len(corrected) / total)


if __name__ == '__main__':
    baseline()
    upper_bound()
    missing = rough_evaluation(first_round_res, second_round_res)
    calculate_at_least_one_agent_correct(missing)
    pass
