import os
import sys

from data.methods2test import Method2Test

sys.path.extend(['.', '..'])
import yaml, json
from dotmap import DotMap
from tqdm import tqdm
from agents.base.llm import DeepSeek
from agents.Generator_Impls import AutoCoTGenerator
import data.methods2test as m2t
import random

random.seed(666)


def AutoCoTAgent_worker(instances, config, pid, output_base):
    model = DeepSeek(config)
    generator = AutoCoTGenerator(model)
    output_file = os.path.join(output_base, 'autocot_agent_results_part_{}.jsonl'.format(pid))
    writer = open(output_file, 'w', encoding='utf-8')
    for _,group in tqdm(instances, desc=f'Generating response'):
        instance, expected_value, raw_assertion, processed_assertion = group
        focal_method = instance.focal_method.body
        test_case = instance.test_case.body
        test_prefix = test_case.replace(raw_assertion, processed_assertion)
        response = generator.generate_assertEquals(focal_method=focal_method, test_prefix=test_prefix, allow_explain=False)
        instance.agent_response = response
        writer.write(json.dumps(instance.toDict(), ensure_ascii=False) + '\n')
    writer.close()
    pass


if __name__ == '__main__':
    code_base = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
    with open(os.path.join(code_base, 'config/basic_config.yaml'), 'r') as reader:
        config = DotMap(yaml.load(reader, Loader=yaml.FullLoader))
    data = Method2Test(config).load_retrieval_data(top_k=1)
    # randomly sample data for inferencing
    random.shuffle(data)

    output_base = os.path.join(code_base, 'results')
    if not os.path.exists(output_base): os.makedirs(output_base)
    AutoCoTAgent_worker(data[:10], config, 0, output_base)
    pass
