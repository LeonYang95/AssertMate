import sys

sys.path.extend(['.', '..'])

from abc import ABC, abstractmethod


class Dataset(ABC):
    def __init__(self, eval_base, source_base, retrieval_res_file):
        self.eval_base = eval_base
        self.retrieval_res_file = retrieval_res_file
        self.source_base = source_base

    @abstractmethod
    def load(self):
        pass

    @abstractmethod
    def load_retrieval_data(self):
        pass

    @abstractmethod
    def load_retrieval_mapping(self, top_k=1):
        pass

    @abstractmethod
    def load_one_instance_from_retrieval_data(self, id):
        pass
