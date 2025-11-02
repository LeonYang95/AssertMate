import os
import sys

sys.path.extend(['.', '..'])
import yaml, json, multiprocessing
from dotmap import DotMap
from tqdm import tqdm
from agents.base.llm import DeepSeek
from agents.Generator_Impls import RAGGenerator

import data.methods2test as m2t
import random

random.seed(666)


def RAGAgent_worker(dual_instances, config, pid, output_base, sample=False):
    """
    Worker function to process instances using a RAG-based generator and write results to a file.

    Args:
        dual_instances (list): List of instances to process, each instance contains two separate instances, one of the retrieved similar instance, and the other one is the taget to be processed.
        config (DotMap): Configuration object.
        pid (int): Process ID for the worker.
        output_base (str): Base directory for output files.
        sample (bool, optional): If True, process only the first 10 instances. Defaults to False.
    """
    model = DeepSeek(config)
    generator = RAGGenerator(model)
    output_file = os.path.join(output_base, 'rag_agent_results_part_{}.jsonl'.format(pid))
    if sample: dual_instances = dual_instances
    writer = open(output_file, 'w', encoding='utf-8')
    for retrieved_group, target_group in tqdm(dual_instances, desc=f'Running thread {pid}'):
        # target information preparation
        instance, expected_value, raw_assertion, processed_assertion = target_group
        focal_method = instance.focal_method.body
        test_case = instance.test_case.body
        test_prefix = test_case.replace(raw_assertion, processed_assertion)

        retrieved_instance = None
        if retrieved_group is not None:
        # retrieved information preparation
            retrieved_instance, retrieved_expected_value, retrieved_raw_assertion, retrieveed_processed_assertion = retrieved_group
            retrieved_focal_method = retrieved_instance.focal_method.body
            retrieved_test_case = retrieved_instance.test_case.body
            retrieved_test_prefix = retrieved_test_case.replace(retrieved_raw_assertion, retrieveed_processed_assertion)

            response = generator.generate_assertEquals(
                retrieved_focal_method=retrieved_focal_method,
                retrieved_test_prefix=retrieved_test_prefix,
                retrieved_ground_truth=retrieved_expected_value,
                focal_method=focal_method,
                test_prefix=test_prefix
            )
        else:
            response = generator.generate_assertEquals(
                focal_method=focal_method,
                test_prefix=test_prefix,
                retrieved_focal_method = None,
                retrieved_test_prefix = None,
                retrieved_ground_truth = None,
            )


        # record result.
        instance.retrieved_instance = retrieved_instance if retrieved_instance else {}
        instance.agent_response = response
        writer.write(json.dumps(instance.toDict(), ensure_ascii=False) + '\n')
    writer.close()
    pass


if __name__ == '__main__':
    code_base = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
    with open(os.path.join(code_base, 'config/basic_config.yaml'), 'r') as reader:
        config = DotMap(yaml.load(reader, Loader=yaml.FullLoader))
    debug = False
    data = m2t.load_retrieval_data(config)

    # randomly sample data for inferencing
    random.shuffle(data)

    output_base = os.path.join(code_base, 'results')
    if not os.path.exists(output_base): os.makedirs(output_base)
    num_process = 5
    num_per_chunk = len(data) // num_process
    num_per_chunk += 1
    chunks = [data[i * num_per_chunk: (i + 1) * num_per_chunk] for i in range(num_process)]
    assert len(chunks) == num_process

    if debug:
        RAGAgent_worker(chunks[0], config, 0, output_base, debug)
        pass
    else:
        jobs = []
        for pid, chunk in enumerate(chunks):
            p = multiprocessing.Process(target=RAGAgent_worker, args=(chunk, config, pid, output_base, True))
            jobs.append(p)
            p.start()

        for job in jobs:
            job.join()

        writer = open(os.path.join(output_base, 'rag_agent_results.jsonl'), 'w', encoding='utf-8')
        for i in range(num_process):
            output_file = os.path.join(output_base, 'rag_agent_results_part_{}.jsonl'.format(i))
            assert os.path.exists(output_file)
            with open(output_file, 'r', encoding='utf-8') as reader:
                for line in reader:
                    if line.strip() == '': continue
                    writer.write(line)
            os.remove(output_file)
        writer.close()

    pass
