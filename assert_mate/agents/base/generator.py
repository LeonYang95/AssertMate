import pickle
from abc import ABC, abstractmethod

from loguru import logger


class Generator(ABC):
    def __init__(self, model, debate_sys_prompt):
        self._history = []
        self.model = model
        self.character_to_id = {
            'CoTGenerator': 1,
            'AutoCoTGenerator': 2,
            'NaiveGenerator': 3,
            'RAGGenerator': 4,
            'FourStepCoTGenerator': 5
        }
        self.generator2user = {
            'RAGGenerator': 'user1',
            'NaiveGenerator': 'user2',
            'FourStepCoTGenerator': 'user3'
        }
        self._candidate_dict = {
            'number': '0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 200, 404, 500',
            'boolean': 'true, false'
        }
        self.debate_system_prompt = debate_sys_prompt

    def _record_history(self, role, content):
        self._history.append({'role': role, 'content': content})

    @property
    def history(self):
        return self._history

    def update_history(self, history):
        self._history = pickle.loads(pickle.dumps(history))

    @abstractmethod
    def generate_assertEquals(self, **kwargs):
        pass

    @abstractmethod
    def generate_assertBoolean(self, **kwargs):
        pass

    @abstractmethod
    def generate_assertNullValue(self, **kwargs):
        pass

    def clear_history(self):
        self._history.clear()

    @abstractmethod
    def refine(self, **kwagrs):
        pass

    def refine_no_judge(self, **kwargs) -> str:
        try:
            assert 'prev_responses' in kwargs
        except AssertionError:
            logger.error('Missing required arguments: prev_responses')
            exit(-1)
        if 'test_case_local_variables' in kwargs:
            vars = kwargs['test_case_local_variables']
        else:
            vars = []
        first_round_responses = kwargs['prev_responses']
        first_round_response = ''
        for character, response in first_round_responses.items():
            if character == self.__class__.__name__:
                continue
            first_round_response += f'- **Colleague{self.character_to_id[character]}**: {response}\n'
            pass
        # First round: Understand the intention of the focal method
        messages = self.history
        var_hints = '\n'.join(vars)
        refine_instruction = f"Now you and your collaborators seem to have different opinion on what to fill in the `<expected_value>`.\n" + \
                             f"Their answers are:\n{first_round_response}\n" + \
                             f"Please rethink your answer and provide a refined one.\n"
        if var_hints != '':
            refine_instruction += f"Here are some local variables defined in the test case, you may need them:\n```java\n{var_hints}\n```\n"
            refine_instruction += 'Please write down your refined answer.'

        messages.append({
            'role': 'user',
            'content': refine_instruction
        })
        response = self.model.get_response_with_prefix(messages=messages, prefix='```java\nassertEquals(')
        self._history = pickle.loads(pickle.dumps(messages))
        self._record_history('assistant', response)
        return response

    def clarify_answer(self) -> str:
        new_messages = self.history + [{
            'role': 'user',
            'content': 'OK, I understand your thoughts, now I need a short answer of what does the assertion finally look like. Please write down your answer.'
        }]
        self._history = pickle.loads(pickle.dumps(new_messages))
        return self.model.get_response_with_prefix(new_messages)

    def type_to_predefined_candidates(self, expected_value_type):
        return self._candidate_dict.get(expected_value_type, None)

    def _group_debate_messages(self, focal_method: str, test_prefix: str, statements: dict) -> list:
        instruction = 'You and other users are asked to accomplish the following test case:\n```java\n' + test_prefix + '\n```\n'
        instruction += 'And the focal method (i.e., the method under test) is:\n```java\n' + focal_method + '\n```\n\n'
        instruction += 'Here are the answers from the users:\n'
        for character, statement in statements.items():
            instruction += f'- {character}: {statement}\n'
        cur_user = ''
        other_users = []
        for generator, user in self.generator2user.items():
            if self.__class__.__name__ == generator:
                cur_user = user
            else:
                other_users.append(user)
        other_user_str = ' and '.join(other_users)
        instruction += (
            f'\n\nNow you are in a debate with other users. Remember you are **{cur_user}**. What do you think about the opinions of {other_user_str}? '
            'more reasonable? or more unreasonable? '
            'Please give your final answer of the assertion statement starting with “I think the answer should be” and explain very shortly starting with “Explanation: ”.')
        messages = []
        messages.append({
            'role': 'system',
            'content': self.debate_system_prompt
        })
        messages.append({
            'role': 'user',
            'content': instruction
        })
        return messages

    def debate(self, **kwargs):
        focal_method = kwargs['focal_method']
        test_prefix = kwargs['test_prefix']
        statements = kwargs['statements']
        if 'prefix' in kwargs:
            prefix = kwargs['prefix']
        else:
            prefix = 'I think the answer should be:\n```java\nassertEquals('
        messages = self._group_debate_messages(
            focal_method=focal_method, test_prefix=test_prefix,
            statements=statements)
        response = self.model.get_response_with_prefix(
            messages=messages,
            prefix=prefix)
        self._history = messages
        self._record_history(role='assistant', content=response)
        return response
