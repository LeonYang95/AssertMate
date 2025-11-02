import os
import sys

sys.path.extend(['.', '..'])
import yaml
from dotmap import DotMap
from tqdm import tqdm
from agents.base.llm import DeepSeek
from agents.Generator_Impls import NaiveGenerator
import data.methods2test as m2t
import random

random.seed(666)


def NaiveAgent_worker(instances, config):
    model = DeepSeek(config)
    generator = NaiveGenerator(model)
    for group in tqdm(instances, desc=f'Running'):
        instance, expected_value, raw_assertion, processed_assertion = group
        focal_method = instance.focal_method.body
        test_case = instance.test_case.body
        test_prefix = test_case.replace(raw_assertion, processed_assertion)
        response = generator.generate_assertEquals(focal_method=focal_method, test_prefix=test_prefix, allow_explain=False)
        instance.agent_response = response
    pass


if __name__ == '__main__':
    code_base = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
    with open(os.path.join(code_base, 'config/basic_config.yaml'), 'r') as reader:
        config = DotMap(yaml.load(reader, Loader=yaml.FullLoader))
    debug = True
    data = m2t.load(config)

    # randomly sample data for inferencing
    random.shuffle(data)

    output_base = os.path.join(code_base, 'results')
    NaiveAgent_worker(data[:5], config)
    pass
