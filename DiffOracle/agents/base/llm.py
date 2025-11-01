import sys
import openai
import numpy as np
from openai import OpenAI
from loguru import logger
from abc import abstractmethod, ABC
import requests
import pickle
sys.path.extend(['.', '..'])

from utils.postprocessing import extract_assertion_from_response

class LLM(ABC):
    @abstractmethod
    def get_response(self, messages) -> str:
        pass

    @abstractmethod
    def fim_response(self, prompt, suffix, max_tokens=4096) -> str:
        pass

    @abstractmethod
    def get_response_with_prefix(self, messages, prefix) -> str:
        pass

    @abstractmethod
    def get_multiple_responses_with_prefix(self, messages, prefix):
        pass


class DeepSeek(LLM):
    def __init__(self, config):
        super().__init__()
        try:
            self.api_key = config.deepseek.key
            self.base_url = config.deepseek.api
            openai.api_key = config.deepseek.key
            openai.base_url = config.deepseek.api
            self.temperature = config.deepseek.temperature
            self.top_p = config.deepseek.top_p
            self.max_tokens = config.deepseek.max_tokens
            self.model = config.deepseek.model
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            self.eos = config.deepseek.eos
            self.assistant_response_header = config.deepseek.response_header
        except Exception:
            logger.error(
                "Error loading configuration: llm.key or llm.api, please check the configuration file.")
            exit(-1)

    def get_response(self, messages):
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                # stream=False,
                temperature=self.temperature,
                # top_p=self.top_p,
                max_tokens=self.max_tokens,
                stop=self.eos
            )
        except openai.APIError as apierror:
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    # stream=False,
                    temperature=self.temperature,
                    # top_p=self.top_p,
                    max_tokens=self.max_tokens,
                    stop=self.eos
                )
            except openai.APIError:
                return ''
        return response.choices[0].message.content

    def get_response_with_prefix(self, messages, prefix='```java\nassertEquals('):
        new_message = pickle.loads(pickle.dumps(messages))
        # fim_url = self.base_url + '/beta'
        fim_url = self.base_url
        # extend_client = OpenAI(api_key=self.api_key, base_url=fim_url)
        prompt = self.tokenizer.apply_chat_template(
            new_message, tokenize=False)
        prompt += self.assistant_response_header + prefix
        completion = openai.completions.create(
            model=self.model, prompt=prompt, max_tokens=4096, stop=self.eos)
        return prefix + completion.choices[0].text
        # return self.get_response_with_confidence(messages, prefix)

    def fim_response(self, prompt, suffix, max_tokens=4096):
        fim_url = self.base_url + '/beta'
        fim_client = OpenAI(api_key=self.api_key, base_url=fim_url)
        response = fim_client.completions.create(
            model="deepseek-chat",
            prompt=prompt,
            suffix=suffix,
            max_tokens=max_tokens
        )
        return response.choices[0].text

    def get_multiple_responses_with_prefix(self, messages, prefix='```java\nassertEquals(', best_of=10):
        try:
            new_message = pickle.loads(pickle.dumps(messages))
            fim_url = self.base_url
            prompt = self.tokenizer.apply_chat_template(
                new_message, tokenize=False)
            prompt += self.assistant_response_header + prefix
            completion = openai.completions.create(
                model=self.model, prompt=prompt, max_tokens=1024,
                temperature=1.0,
                stop=self.eos,
                logprobs=1,
                n=best_of,
            )
            choices = [completion.choices[i].text for i in range(best_of)]
            probs = [self.analyze_prob(
                choice.logprobs.tokens, choice.logprobs.token_logprobs) for choice in completion.choices]
            responses = [prefix + choice for choice in choices]
            return responses, probs
        except openai.BadRequestError as e:
            logger.error(f'Http request failed, Error: {str(e)}')
            return [],[]

    def analyze_prob(self, tokens, token_logprobs):
        probs = []
        for token, prob in zip(tokens, token_logprobs):
            if token == '```':
                break
            probs.append(prob)
            pass
        final_prob = np.average(np.asarray(probs))
        final_prob = np.round(np.exp(final_prob)*100, 2)
        return final_prob

