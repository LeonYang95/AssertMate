import pickle

import torch
from tqdm import *
from transformers import AutoTokenizer, AutoModel

device = torch.device('mps')
model_base = '/Users/yanglin/Documents/Models/codet5-base'


def embed(input_list):
    # 加载预训练的模型和分词器，并将模型移动到设备
    tokenizer = AutoTokenizer.from_pretrained(model_base)
    model = AutoModel.from_pretrained(model_base).to(device)
    embeddings = []
    for code in tqdm(input_list):
        # 编码输入文本，并将输入数据移动到设备
        inputs = tokenizer(code, return_tensors='pt').input_ids.to(device)

        # 获取模型的输出
        with torch.no_grad():
            outputs = model.encoder(inputs)

        # 提取最后一层隐藏状态
        last_hidden_states = outputs.last_hidden_state

        # 对隐藏状态进行池化（取平均）以获得句子级别的向量表示
        sentence_embedding = torch.mean(last_hidden_states, dim=1).cpu().numpy()
        embeddings.append(pickle.loads(pickle.dumps(sentence_embedding.tolist()[0])))
    return embeddings
