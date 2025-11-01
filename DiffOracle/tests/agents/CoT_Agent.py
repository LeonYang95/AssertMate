import os
import sys

sys.path.extend(['.', '..'])
import yaml, json, multiprocessing
from dotmap import DotMap
from tqdm import tqdm
from agents.base.llm import DeepSeek
from agents.Generator_Impls import CoTGenerator
import data.methods2test as m2t
import random
import time

random.seed(666)


def CoTAgent_worker(instances, config, pid, output_base):
    model = DeepSeek(config)
    generator = CoTGenerator(model)
    output_file = os.path.join(output_base, 'cot_agent_results_part_{}.jsonl'.format(pid))
    writer = open(output_file, 'w', encoding='utf-8')
    for group in tqdm(instances, desc=f'Running thread {pid}'):
        instance, expected_value, raw_assertion, processed_assertion = group
        focal_method = instance.focal_method.body
        test_case = instance.test_case.body
        test_prefix = test_case.replace(raw_assertion, processed_assertion)
        response = generator.generate_assertEquals(focal_method=focal_method, test_prefix=test_prefix)
        instance.agent_response = response
        writer.write(json.dumps(instance.toDict(), ensure_ascii=False) + '\n')
    writer.close()
    pass


if __name__ == '__main__':
    code_base = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
    with open(os.path.join(code_base, 'config/basic_config.yaml'), 'r') as reader:
        config = DotMap(yaml.load(reader, Loader=yaml.FullLoader))
    debug = True
    data = m2t.load(config)

    # randomly sample data for inferencing
    random.shuffle(data)
    output_base = os.path.join(code_base, 'results')
    if not os.path.exists(output_base): os.makedirs(output_base)

    if debug:
        CoTAgent_worker(data[:10], config, 0, output_base)
        pass
    else:
        num_process = 5
        num_per_chunk = len(data) // num_process
        num_per_chunk += 1
        chunks = [data[i * num_per_chunk: (i + 1) * num_per_chunk] for i in range(num_process)]
        assert len(chunks) == num_process
        jobs = []
        for pid, chunk in enumerate(chunks):
            p = multiprocessing.Process(target=CoTAgent_worker, args=(chunk, config, pid, output_base))
            jobs.append(p)
            p.start()

        for job in jobs:
            job.join()

        writer = open(os.path.join(output_base, 'cot_agent_results.jsonl'), 'w', encoding='utf-8')
        for i in range(num_process):
            output_file = os.path.join(output_base, 'cot_agent_results_part_{}.jsonl'.format(i))
            assert os.path.exists(output_file)
            with open(output_file, 'r', encoding='utf-8') as reader:
                for line in reader:
                    if line.strip() == '': continue
                    writer.write(line)
            os.remove(output_file)
        writer.close()

    pass
