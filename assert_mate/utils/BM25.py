import math
import re
from collections import Counter

import javalang


def camel_case_split(identifier):
    """
    将驼峰命名的标识符拆分为单词列表。
    例如，"camelCaseSplit" 会被拆分为 ["camel", "Case", "Split"]。
    """
    # 去除字符串
    if identifier.startswith('"'):
        return [identifier]
    # 使用正则表达式进行拆分
    words = re.findall(
        r'[A-Z]+(?=[A-Z][a-z0-9]|[0-9]|$)|[A-Z]?[a-z0-9]+|[A-Z]+|[0-9]+',
        identifier
    )
    return words


def tokenize_code(text):
    """
    针对代码文本的分词函数，处理驼峰命名和其他情况。
    """
    # 首先按照非字母数字字符分割
    tokens = [tok.value for tok in javalang.tokenizer.tokenize(text)]
    processed_tokens = []
    for token in tokens:
        if token:
            # 处理驼峰命名
            camel_tokens = camel_case_split(token)
            # 将拆分后的词项转为小写，统一格式
            processed_tokens.extend([t.lower() for t in camel_tokens if t])
    return processed_tokens


def bm25_similarity(doc1, doc2, k1=1.5, b=0.75):
    """
    计算两段代码文本之间的BM25相似度。

    参数：
    - doc1, doc2: 两段代码文本（字符串）。
    - k1, b: BM25算法的参数，默认设置为常用值。

    返回：
    - 相似度分数（浮点数）。
    """

    tokens1 = tokenize_code(doc1)
    tokens2 = tokenize_code(doc2)

    # 构建文档集合
    documents = [tokens1, tokens2]

    # 计算平均文档长度
    avgdl = sum(len(doc) for doc in documents) / len(documents)

    # 统计词项在文档中的频率和文档频率
    term_frequencies = [Counter(doc) for doc in documents]

    # 计算文档频率（包含该词项的文档数）
    df = {}
    for term in set(tokens1 + tokens2):
        df[term] = sum(1 for tf in term_frequencies if term in tf)

    # 计算逆文档频率IDF
    N = len(documents)
    idf = {}
    for term, freq in df.items():
        # 使用BM25的IDF公式
        idf[term] = math.log(1 + (N - freq + 0.5) / (freq + 0.5))

    # 定义BM25打分函数
    def bm25_score(query_tokens, doc_tokens, doc_tf):
        score = 0.0
        doc_len = len(doc_tokens)
        for term in query_tokens:
            if term in doc_tf:
                tf = doc_tf[term]
                numerator = idf[term] * tf * (k1 + 1)
                denominator = tf + k1 * (1 - b + b * doc_len / avgdl)
                score += numerator / denominator
        return score

    # 计算从doc1到doc2的BM25相似度
    score1 = bm25_score(tokens1, tokens2, term_frequencies[1])
    # 计算从doc2到doc1的BM25相似度
    score2 = bm25_score(tokens2, tokens1, term_frequencies[0])

    # 取平均值作为对称的相似度分数
    similarity = (score1 + score2) / 2

    return similarity


# 示例使用
if __name__ == "__main__":
    code_text1 = '''
    def addNumbers(PDF, b):
        return PDF + b
    '''

    code_text2 = '''
    def sum_numbers(x, y):
        result = x + y
        return result
    '''

    similarity_score = bm25_similarity(code_text1, code_text2)
    print(f"两段代码的BM25相似度为: {similarity_score}")
