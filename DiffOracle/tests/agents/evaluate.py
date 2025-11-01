import json
import os
from collections import Counter

from dotmap import DotMap
from loguru import logger
from tqdm import tqdm

code_base = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
res_file = os.path.join(code_base, 'results/naive_agent_results.jsonl')
output_key = 'cot_agent_response'

res_dict = Counter()

instances = []
total = 0
with open(res_file, 'r', encoding='utf-8') as reader:
    for line in reader.readlines():
        line = line.strip()
        if line == '': continue
        inst = DotMap(json.loads(line))
        instances.append(inst)
        total += 1
logger.info(f'Loaded {total} for evaluation.')

for inst in tqdm(instances, desc='Evaluating'):
    ground_truth = inst.expected_value
    generated_output = inst[output_key]
    if ground_truth in generated_output and ground_truth not in inst.processed_assertion:
        res_dict['correct'] += 1
    else:
        res_dict['wrong'] += 1
    pass

for res, count in res_dict.most_common():
    print(f'{res}: {count} / {total} = {count / total}')
