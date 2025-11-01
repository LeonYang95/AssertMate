import os
import sys

import javalang.tokenizer

sys.path.extend(['.', '..'])
import json
import pickle
import multiprocessing
import yaml
from loguru import logger
from dotmap import DotMap
from tqdm import tqdm
from data.base.dataset_factory import dataset_factory

code_base = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
debug = True
dataset_base = '/Users/yanglin/Documents/Projects/data/AssertionGenerationDatasets/NewDataSet'
methods2test_base = '/Users/yanglin/Documents/Projects/data/methods2test/dataset'




def Jaccard_similarity(input: set, target: set) -> float:
    """
    Jaccard similarity between two sets
    """
    intersection = len(input.intersection(target))
    union = len(input.union(target))
    return intersection / union


def load_atlas_instances(source_file) -> list:
    instances = []
    with open(source_file, 'r', encoding='utf-8') as reader:
        idx = 0
        for line in reader.readlines():
            instances.append({'idx': idx,
                              'text': line.strip()})
            idx += 1
            pass
    return instances


def atlas_retrieve():
    source_file = os.path.join(dataset_base, 'Training/testMethods.txt')
    source_instances = load_atlas_instances(source_file)
    source_file = os.path.join(dataset_base, 'Testing/testMethods.txt')
    test_instances = load_atlas_instances(source_file)

    num_processes = 10
    num_per_chunk = len(test_instances) // num_processes
    chunks = []
    for i in range(num_processes):
        chunks.append(test_instances[i * num_per_chunk:(i + 1) * num_per_chunk])

    jobs = []
    for pid, chunk in enumerate(chunks):
        p = multiprocessing.Process(target=_atlas_retrieve, args=(pid, chunk, source_instances))
        jobs.append(p)
        p.start()

    for job in jobs:
        job.join()

    with open(os.path.join(code_base, 'data/ATLAS_retrieval_results_top_1.jsonl'), 'w',
              encoding='utf-8') as writer:
        for pid in range(num_processes):
            with open(os.path.join(code_base, f'data/ATLAS_retrieval-{pid}-results.jsonl'), 'r',
                      encoding='utf-8') as reader:
                for line in reader.readlines():
                    writer.write(line)
            os.remove(os.path.join(code_base, f'results/ATLAS_retrieval-{pid}-results.jsonl'))


def _atlas_retrieve(pid, tgt_instances, src_instances):
    with open(os.path.join(code_base, f'results/ATLAS_retrieval-{pid}-results.jsonl'), 'w',
              encoding='utf-8') as writer:
        for tgt_item in tqdm(tgt_instances, desc=f'{pid} processing:'):
            tgt_inst = tgt_item['text']
            tgt_idx = tgt_item['idx']
            best_sim = -1
            best_idx = -1
            tgt_inst = set(tgt_inst.split())
            for src_item in src_instances:
                src_idx, src_inst = src_item['idx'], src_item['text']
                src_inst = set(src_inst.split())
                sim = Jaccard_similarity(tgt_inst, src_inst)
                if sim > best_sim:
                    best_idx = src_idx
                    best_sim = sim
                    if best_sim == 1.0:
                        break
            assert best_idx != -1

            writer.write(
                json.dumps({'tgt_idx': tgt_idx, 'src_idx': best_idx, 'sim': best_sim}, ensure_ascii=False) + '\n')
    pass


def traverse_methods2test_data(folder):
    instances = []
    for root, dirs, files in os.walk(folder):
        for file in files:
            if not file.endswith('.json'):
                continue
            with open(os.path.join(root, file), 'r', encoding='utf-8') as reader:
                inst = json.loads(reader.read())
                instances.append({
                    'id': file.split('.')[0],
                    'focal_method': inst['focal_method']['body'],
                    'test_case': inst['test_case']['body']
                })
            if len(instances) % 1000 == 0:
                logger.info(f'Processed {len(instances)} src instances.')
    return instances


def load_methods2test_data_by_project(target_base):
    project2instances = {}
    for root, dirs, files in os.walk(target_base):
        for file in files:
            if not file.endswith('.json'):
                continue
            with open(os.path.join(root, file), 'r', encoding='utf-8') as reader:
                inst = json.loads(reader.read())
                project = file.split('_')[0]
                if project not in project2instances:
                    project2instances[project] = []
                project2instances[project].append({
                    'id': file.split('.')[0],
                    'focal_method': inst['focal_method']['body'],
                    'test_case': inst['test_case']['body']
                })
    return project2instances


def methods2test_cross_project_retrieve(target_ids=None):
    target_base = os.path.join(methods2test_base, 'test')
    target_instances = traverse_methods2test_data(target_base)
    if target_ids:
        new_target_instances = []
        for inst in target_instances:
            if inst['id'] in target_ids:
                new_target_instances.append(inst)
        target_instances = new_target_instances
        logger.info(f'Filtered {len(target_instances)} instances after filtering.')

    logger.info('Start loading source instances.')
    src_base = os.path.join(methods2test_base, 'train')
    src_instances = traverse_methods2test_data(src_base)
    num_process = 10
    num_per_chunk = len(target_instances) // num_process + 1
    processes = []


    for i in range(num_process):
        chunk_item_list = target_instances[i * num_per_chunk:(i + 1) * num_per_chunk]
        p = multiprocessing.Process(
            target=_methods2test_cross_project_retrieve,
            args=(chunk_item_list, src_instances, i)
        )
        processes.append(p)
        p.start()

    for p in processes:
        p.join()

    with open(os.path.join(code_base, 'data/methods2test-cross_project-by_test_case-jaccard-rankings.jsonl'), 'w',
              encoding='utf-8') as writer:
        for i in range(num_process):
            sub_process_ranking_file = os.path.join(code_base, f'data/tmp-{i}.json')
            with open(sub_process_ranking_file, 'r', encoding='utf-8') as reader:
                sub_process_rankings = json.load(reader)
            for key, value in sub_process_rankings.items():
                writer.write(json.dumps({key: value}, ensure_ascii=False) + '\n')
            os.remove(sub_process_ranking_file)

    pass


def methods2test_in_project_retrieve():
    target_base = os.path.join(methods2test_base, 'test')
    target_instances = load_methods2test_data_by_project(target_base)
    num_process = 5
    num_per_chunk = len(target_instances) // num_process + 1
    processes = []

    for i in range(num_process):
        chunk_item_list = list(target_instances.items())[i * num_per_chunk:(i + 1) * num_per_chunk]
        p = multiprocessing.Process(target=_methods2test_in_project_retrieve,
                                    args=(dict(chunk_item_list), i))
        processes.append(p)
        p.start()

    for p in processes:
        p.join()

    with open(os.path.join(code_base, 'data/methods2test-in_project-by_test_case-bm25-rankings.jsonl'), 'w',
              encoding='utf-8') as writer:
        for i in range(num_process):
            sub_process_ranking_file = os.path.join(code_base, f'data/tmp-{i}.json')
            with open(sub_process_ranking_file, 'r', encoding='utf-8') as reader:
                sub_process_rankings = json.load(reader)
            for key, value in sub_process_rankings.items():
                writer.write(json.dumps({key: value}, ensure_ascii=False) + '\n')
            os.remove(sub_process_ranking_file)

    pass


def _methods2test_in_project_retrieve(projects, pid=0):
    rankings = {}
    for project, insts in projects.items():
        if len(insts) == 1:
            inst = insts[0]
            rankings[inst['id']] = []
        elif len(insts) == 2:
            inst1, inst2 = insts
            rankings[inst1['id']] = [{'id': inst2['id'], 'sim': -1.0}]
            rankings[inst2['id']] = [{'id': inst1['id'], 'sim': -1.0}]
        else:
            for tgt_inst in tqdm(insts):
                sim_inst_id = None
                max_sim = -1
                # tgt_inst_tokens = set([tok.value for tok in javalang.tokenizer.tokenize(tgt_inst['focal_method'])])
                tgt_inst_tokens = set()
                tgt_inst_tokens = tgt_inst_tokens.union(
                    set([tok.value for tok in javalang.tokenizer.tokenize(tgt_inst['test_case'])])
                )
                for src_inst in insts:
                    if src_inst['id'] == tgt_inst['id']:
                        continue

                    src_inst_tokens = set([
                        tok.value for tok in javalang.tokenizer.tokenize(src_inst['test_case'])
                    ])

                    sim = Jaccard_similarity(
                        tgt_inst_tokens,
                        src_inst_tokens
                    )
                    # sim = bm25_similarity(
                    #     tgt_inst['focal_method'],
                    #     src_inst['focal_method']
                    # )
                    if sim > max_sim:
                        max_sim = pickle.loads(pickle.dumps(sim))
                        sim_inst_id = pickle.loads(pickle.dumps(src_inst['id']))
                        pass
                    pass
                rankings[tgt_inst['id']] = [{'id': sim_inst_id, 'sim': max_sim}]
                pass
            pass
        pass
    with open(os.path.join(code_base, f'data/tmp-{pid}.json'), 'w',
              encoding='utf-8') as writer:
        writer.write(json.dumps(rankings, ensure_ascii=False))


def _methods2test_cross_project_retrieve(tgt_insts, src_insts, pid):

    rankings = {}
    for tgt_inst in tqdm(tgt_insts, desc=f'PID-{pid}'):
        sim_inst_id = None
        max_sim = -1
        # tgt_inst_tokens = set([tok.value for tok in javalang.tokenizer.tokenize(tgt_inst['focal_method'])])
        tgt_inst_tokens = set()
        tgt_inst_tokens = tgt_inst_tokens.union(
            set([tok.value for tok in javalang.tokenizer.tokenize(tgt_inst['test_case'])])
        )
        for src_inst in src_insts:
            if src_inst['id'] == tgt_inst['id']:
                continue
            try:
                src_inst_tokens = set([
                    tok.value for tok in javalang.tokenizer.tokenize(src_inst['test_case'])
                ])
            except javalang.tokenizer.LexerError:
                continue

            sim = Jaccard_similarity(
                tgt_inst_tokens,
                src_inst_tokens
            )
            # sim = bm25_similarity(
            #     tgt_inst['focal_method'],
            #     src_inst['focal_method']
            # )
            if sim > max_sim:
                max_sim = pickle.loads(pickle.dumps(sim))
                sim_inst_id = pickle.loads(pickle.dumps(src_inst['id']))
                pass
            pass
        rankings[tgt_inst['id']] = [{'id': sim_inst_id, 'sim': max_sim}]
    pass
    with open(os.path.join(code_base, f'data/tmp-{pid}.json'), 'w',
              encoding='utf-8') as writer:
        writer.write(json.dumps(rankings, ensure_ascii=False))


if __name__ == '__main__':
    # atlas_retrieve()
    with open(os.path.join(code_base, 'config/basic_config.yaml'), 'r') as reader:
        config = DotMap(yaml.load(reader, Loader=yaml.FullLoader))

    ds = dataset_factory(config, 'methods2test')
    data = ds.load_retrieval_data(top_k=1)
    target_ids = []
    for groups in data:
        _, target_group = groups
        inst, _, _, _ = target_group
        target_ids.append(inst.id)

    methods2test_cross_project_retrieve(target_ids)
