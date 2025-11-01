import sys

sys.path.extend(['.', '..'])
from dotmap import DotMap
from data.base.datasets import Dataset
from data.methods2test import Method2Test
from data.defects4j import Defects4J, Integration_Defects4J
from data.atlas import ATLAS


def dataset_factory(config: DotMap, dataset: str) -> None | Dataset:
    if dataset.lower() == 'methods2test':
        return Method2Test(config)
    if dataset.lower() == 'atlas':
        return ATLAS(config)
    if dataset.lower() == 'defects4j':
        return Defects4J(config)
    if dataset.lower() == 'defects4j_integration':
        return Integration_Defects4J(config)
    else:
        return None
