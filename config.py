import argparse
import os
import openai
import numpy as np
from openai import OpenAI
from loguru import logger
from transformers import AutoTokenizer
from abc import abstractmethod, ABC
import requests
import pickle

code_base = os.path.abspath(os.path.dirname(__file__))
logger.add(os.path.join(code_base, "logs/debug.log"), rotation="1 MB", level="DEBUG", encoding="utf-8")

