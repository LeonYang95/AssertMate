import sys

sys.path.extend(['.', '..'])
import random

random.seed(666)

known_assertions = [
    'assertEquals',
    'assertTrue',
    'assertFalse',
    'assertNull',
    'assertNotNull',
    'assertThat',
    'assertArrayEquals',
    'assertNotEquals',
    'assertThrows',
    'assertSame',
    'assertNotSame',
]
