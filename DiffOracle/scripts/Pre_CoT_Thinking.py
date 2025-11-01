import sys

sys.path.extend(['.', '..'])
import os
import yaml
from multiprocessing import Process, Value, Lock
from dotmap import DotMap
from tqdm import tqdm
import random, json

import data.methods2test as m2t
from agents.Generator_Impls import CoTGenerator
from agents.base.llm import DeepSeek

random.seed(666)

code_base = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
with open(os.path.join(code_base, 'config/basic_config.yaml'), 'r') as reader:
    config = DotMap(yaml.load(reader, Loader=yaml.FullLoader))
model = DeepSeek(config)


def discussion(dual_groups, pid, output_base):
    generator = CoTGenerator(model)
    writer = open(os.path.join(output_base, 'CoT_Thoughts_part_{}.jsonl'.format(pid)), 'w', encoding='utf-8')
    for dual_group in tqdm(dual_groups):
        _, target_group = dual_group
        instance, expected_value, raw_assertion, processed_assertion = target_group
        focal_method = instance.focal_method.body
        id = instance.id
        # First round: Understand the intention of the focal method
        messages = generator.group_messages(generator._intention_prompt(focal_method))
        response = generator.model.get_response(messages=messages)
        record = {
            'id': id,
            'thought': response
        }
        writer.write(json.dumps(record, ensure_ascii=False) + '\n')
    pass


if __name__ == '__main__':
    debug = True
    data = m2t.load_retrieval_data(config)

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
        discussion(chunks[0], 0, output_base)
        pass
    else:
        jobs = []
        for pid, chunk in enumerate(chunks):
            p = Process(target=discussion, args=(chunk, config, pid, output_base, True))
            jobs.append(p)
            p.start()

        for job in jobs:
            job.join()

        writer = open(os.path.join(output_base, 'CoT_Thoughts.jsonl'), 'w', encoding='utf-8')
        for i in range(num_process):
            output_file = os.path.join(output_base, 'CoT_Thoughts_part_{}.jsonl'.format(i))
            assert os.path.exists(output_file)
            with open(output_file, 'r', encoding='utf-8') as reader:
                for line in reader:
                    if line.strip() == '': continue
                    writer.write(line)
            os.remove(output_file)
        writer.close()

    pass
