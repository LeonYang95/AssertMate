import json
import os
from multiprocessing import Manager

from loguru import logger


class MultiProcessingCache():
    def __init__(self, thoughts):
        manager = Manager()
        self._cot_thoughts = manager.dict()
        self._cot_thoughts.update(thoughts)

    @property
    def cot_thoughts(self):
        return self._cot_thoughts

    def update_cot_thoughts(self, add_thought):
        logger.debug(f'Updating thought:{add_thought}')
        self._cot_thoughts.update(add_thought)


def load_cache(code_base):
    if os.path.exists(os.path.join(code_base, 'cache/cot_thoughts.json')):
        logger.debug(f'Load existing cache file.')
        with open(os.path.join(code_base, 'cache/cot_thoughts.json'), 'r', encoding='utf-8') as reader:
            try:
                thoughts = json.load(reader)
                return MultiProcessingCache(thoughts)
            except Exception as e:
                logger.error(f'Load cache file failed due to {e}, creating empty cache object.')
                return MultiProcessingCache({})
    else:
        logger.debug(f'Cache file does not exist, creating empty cache object.')
        return MultiProcessingCache({})


def dump_cache(code_base, cache:dict):
    if not os.path.exists(os.path.join(code_base, 'cache')):
        logger.debug(f'Cache folder does not exist, creat one.')
        os.makedirs(os.path.join(code_base, 'cache'))
    with open(os.path.join(code_base, 'cache/cot_thoughts.json'), 'w', encoding='utf-8') as writer:
        logger.debug('Dumping cache.')
        json.dump(cache, writer, ensure_ascii=False, indent=4)
    logger.debug('Dumped.')
    pass
