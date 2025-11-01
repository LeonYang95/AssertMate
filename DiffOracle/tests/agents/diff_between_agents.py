import json
import os

from dotmap import DotMap
from loguru import logger
from tqdm import tqdm

agent_results = [
    'naive_agent_results.jsonl',
    'cot_agent_results.jsonl',
    'rag_agent_results.jsonl'
]

res_lists = []
union_results = set()
for agent_result in agent_results:
    res = []
    code_base = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
    res_file = os.path.join(code_base, f'results/{agent_result}')
    output_key = 'agent_response'
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
    idx = 0
    for inst in tqdm(instances, desc='Evaluating'):
        ground_truth = inst.expected_value
        generated_output = inst[output_key]
        if ground_truth in generated_output and ground_truth not in inst.processed_assertion:
            res.append(idx)
        idx += 1
        pass
    res_lists.append(set(res))
    union_results = union_results.union(set(res))

diff = res_lists[0].difference(res_lists[1])
print(diff)
diff = res_lists[1].difference(res_lists[0])
print(diff)
diff = res_lists[2].difference(res_lists[0].union(res_lists[1]))
print(diff)
common = res_lists[0].intersection(res_lists[1])
common = common.intersection(res_lists[2])
print(common)
print(len(union_results))
