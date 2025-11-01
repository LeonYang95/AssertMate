import sys

sys.path.extend(['.', '..'])
import os
import yaml
from dotmap import DotMap
from data.base.dataset_factory import dataset_factory


code_base = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
with open(os.path.join(code_base, 'config/basic_config.yaml'), 'r') as reader:
    config = DotMap(yaml.load(reader, Loader=yaml.FullLoader))

if __name__ == '__main__':
    dataset = 'methods2test'
    ds = dataset_factory(config, dataset)
    data = ds.load_retrieval_data(top_k=1)
    for dual_groups in data:
        _, target_group = dual_groups
        instance = target_group[0]
        if 'void' in instance.focal_method:
            print(1)
        else:
            print(2)
