import sys

sys.path.extend(['.','..'])
import json

from utils.postprocessing import extract_assertion_from_response

if __name__ == '__main__':
    with open(
            # '/Users/yanglin/Documents/Projects/DiffOracle/results/no_judge-first_round_speak_up-RAGGenerator-results.jsonl',
            # '/Users/yanglin/Documents/Projects/DiffOracle/results/no_judge-first_round_speak_up-FourStepCoTGenerator-results.jsonl',
            '/results/in_project-RAG/no_judge-first_round_speak_up-NaiveGenerator-results.jsonl',
            'r', encoding='utf-8') as reader:
        for line in reader.readlines():
            line = line.strip()
            if line == '':
                continue
            inst = json.loads(line)
            response = inst['history'][-1].get('content')
            assertion = extract_assertion_from_response(response)
            print(assertion)
    pass


