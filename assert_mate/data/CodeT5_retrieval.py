import os
import sys

import javalang.tokenizer

sys.path.extend(['.', '..'])
import json
import pickle
from tqdm import tqdm
from utils.LLMEmbed import embed
import multiprocessing
from scipy import spatial

code_base = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
debug = True
dataset_base = '/Users/yanglin/Documents/Projects/data/AssertionGenerationDatasets/NewDataSet'
methods2test_base = '/Users/yanglin/Documents/Projects/data/methods2test/dataset'


def cosine_similarity(input1, input2):
    return 1 - spatial.distance.cosine(input1, input2)


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


def load_preprocessing_embeddings() -> dict:
    embedding_mapping = {}
    with open(os.path.join(code_base, 'data/codet5_embed_res.jsonl'), 'r', encoding='utf-8') as reader:
        for line in reader:
            item = json.loads(line)
            embedding_mapping[item['key']] = item['embedding']
    return embedding_mapping


def methods2test_retrieve():
    target_base = os.path.join(methods2test_base, 'test')
    target_instances = load_methods2test_data_by_project(target_base)
    embeddings = load_preprocessing_embeddings()
    num_process = 5
    num_per_chunk = len(target_instances) // num_process + 1
    processes = []

    for i in range(num_process):
        chunk_item_list = list(target_instances.items())[i * num_per_chunk:(i + 1) * num_per_chunk]
        p = multiprocessing.Process(target=_methods2test_retrieve,
                                    args=(dict(chunk_item_list), embeddings, i))
        processes.append(p)
        p.start()

    for p in processes:
        p.join()

    with open(os.path.join(code_base, 'data/methods2test-in_project-codet5-rankings.jsonl'), 'w',
              encoding='utf-8') as writer:
        for i in range(num_process):
            sub_process_ranking_file = os.path.join(code_base, f'data/methods2test-in_project-codet5-rankings-{i}.json')
            with open(sub_process_ranking_file, 'r', encoding='utf-8') as reader:
                sub_process_rankings = json.load(reader)
            for key, value in sub_process_rankings.items():
                writer.write(json.dumps({key: value}, ensure_ascii=False) + '\n')
            os.remove(sub_process_ranking_file)

    pass


def _methods2test_retrieve(projects, embeddings, pid):
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
                for src_inst in insts:
                    if src_inst['id'] == tgt_inst['id']:
                        continue
                    sim = cosine_similarity(
                        embeddings[src_inst['id']],
                        embeddings[tgt_inst['id']]
                    )
                    if sim > max_sim:
                        max_sim = pickle.loads(pickle.dumps(sim))
                        sim_inst_id = pickle.loads(pickle.dumps(src_inst['id']))
                        pass
                    pass
                rankings[tgt_inst['id']] = [{'key': sim_inst_id, 'sim': max_sim}]
                pass
            pass
        pass
    with open(os.path.join(code_base, f'data/methods2test-in_project-codet5-rankings-{pid}.json'), 'w',
              encoding='utf-8') as writer:
        writer.write(json.dumps(rankings, ensure_ascii=False))


def preprocessing():
    target_base = os.path.join(methods2test_base, 'test')
    instances = load_methods2test_data_by_project(target_base)
    embed_inputs = []
    ids = []
    for project, insts in instances.items():
        for inst in insts:
            embed_inputs.append(inst['focal_method'] + ' ' + inst['test_case'])
            ids.append(inst['id'])
    embeddings = embed(embed_inputs)
    with open(os.path.join(code_base, 'data/codet5_embed_res.jsonl'), 'w', encoding='utf-8') as writer:
        for id, embedding in zip(ids, embeddings):
            writer.write(
                json.dumps({'key': id, 'embedding': embedding}, ensure_ascii=False) + '\n'
            )


if __name__ == '__main__':
    # preprocessing()
    methods2test_retrieve()
    pass
