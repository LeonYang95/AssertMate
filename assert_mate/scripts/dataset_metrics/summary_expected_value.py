import sys

sys.path.extend(['.', '..'])
import os
import json
from loguru import logger
from collections import Counter

code_base = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))


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


res_dict = load_jsonl_file_as_dict(os.path.join(code_base, 'results/From_58_Server/no_judge-results.jsonl'))

if __name__ == '__main__':
    expected_value_counter = Counter()
    for id, record in res_dict.items():
        response = record['response']
        expected_value = record['expected_value']
        if expected_value not in response:
            expected_value_counter[expected_value] += 1
        pass
    total = 0
    for value, count in expected_value_counter.most_common():
        total += count
        print(value, count)
    print(total)
