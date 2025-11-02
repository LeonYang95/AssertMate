import sys

sys.path.extend(['.', '..'])
from agents.base.llm import *
from agents.base.generator import Generator
from utils.multi_processing_cache import MultiProcessingCache
import time

class RAGGenerator(Generator):
    def __init__(self, model: LLM):
        self.system_prompt = "You are an expert in software testing, with 10 years of experience. You are very good at writing test cases."
        debate_system_prompt = (
            "You are an expert in software testing, with 10 years of experience. You are very good at writing test cases. "
            "Now you are user1 in a round table debate of three users. "
            "The debate is about choosing a more accurate expected value for an assertion statement. "
            "The opinions of the other two users are not always true, you can ignore any incorrect part of their opinion. "
            "And you can refer to their opinions to revise yours or defend your own. "
            "Please remember there should and must be a more plausible answer in the responses.")
        super().__init__(model, debate_system_prompt)

        pass

    def _construct_instruction(self, focal_method: str, test_prefix: str) -> str:
        instruction = 'Your task is to complete the given test case. The method under testing is \n```java\n' + \
                      focal_method + '\n```\n Here is part of the test case for the above method: \n```java\n' + \
                      test_prefix + '\n```\n'
        instruction += 'Please read the code, and decide what should I place in the <expected_value> part of the assertion.\n'
        # instruction += "Please directly respond the code without any explanation."
        return instruction

    def _construct_instruction_all_in_one(self, focal_method: str, test_prefix: str, retrieved_focal_method: str | None,
                                          retrieved_test_case: str | None) -> str:
        instruction = "Your task is to complete the given test case. The method under testing is \n```java\n" + \
                      focal_method + "\n```\n Here is part of the test case for the above method: \n```java\n" + \
                      test_prefix + "\n```\n"
        if retrieved_focal_method and retrieved_test_case:
            instruction += 'Here is a similar focal method and its corresponding test case, I hope this could help you:\n```java\n' + \
                           retrieved_focal_method + '\n' + retrieved_test_case + '\n```\n'

        instruction += 'Please read my code, compare the differences between my code and the similar focal method. Then, based on the given test case, you can decide what should I put in the <expected_value> part? Please write down the completed assertion and provide a short explaination. You should keep your answer within 200 words. '
        return instruction

    def _construct_instruction_all_in_one_with_code_feature(self, focal_method: str, test_prefix: str,
                                                            retrieved_focal_method: str | None,
                                                            retrieved_test_case: str | None, focal_class_fields,
                                                            focal_class_methods, test_class_fields,
                                                            actual_value: str) -> str:
        instruction = "Your task is to complete the given test case. The method under testing is \n```java\n" + \
                      focal_method + "\n```\n Here is part of the test case for the above method: \n```java\n" + \
                      test_prefix + "\n```\n"
        if len(focal_class_fields) != 0 or len(focal_class_methods) != 0:
            instruction += 'The method is declared in a class with the following fields and methods:\n```java\n'
            if len(focal_class_fields) != 0:
                instruction += '//Defined fields'
                for field in focal_class_fields:
                    instruction += field + '\n'
            if len(focal_class_methods) != 0:
                instruction += '//Defined methods'
                for method in focal_class_methods:
                    instruction += method + '\n'
                instruction += '```\n'

        if len(test_class_fields) != 0:
            instruction += 'The test case is declared in a class with the following fields:\n```java\n'
            for field in test_class_fields:
                instruction += field + '\n'
            instruction += '```\n'
        if retrieved_focal_method and retrieved_test_case:
            instruction += 'Here is a similar focal method and its corresponding test case, I hope this could help you:\n```java\n' + \
                           retrieved_focal_method + '\n' + retrieved_test_case + '\n```\n'
        instruction
        instruction += 'Please read my code, and decide what should I put in the <expected_value> part. You can learn from the given example and help you make decision. '
        instruction += 'Please write down the completed assertion and provide a short explaination. You should keep your answer within 200 words.'
        return instruction

    def _construct_instruction_all_in_one_for_assertBool(self, focal_method: str, test_prefix: str,
                                                         retrieved_focal_method: str | None,
                                                         retrieved_test_case: str | None) -> str:
        instruction = "Your task is to help me add an assertion to help me verify the correctness of a method under testing. The method is \n```java\n" + \
                      focal_method + "\n```\n Here is the test case for the above method: \n```java\n" + \
                      test_prefix + "\n```\n"
        instruction += "Now I need your help on writing one assertion at the `<AssertionPlaceHolder>` line, following the code comment in the test case."
        if retrieved_focal_method and retrieved_test_case:
            instruction += 'Here is a similar focal method and its corresponding test case, I hope this could help you:\n```java\n' + \
                           retrieved_focal_method + '\n' + retrieved_test_case + '\n```\n'
        instruction += 'Please read my code and write an assertion statement in the `<AssertionPlaceHolder>` line.\n' + \
                       "Note that you **MUST** use either `assertTrue()` or `assertFalse()` method to verify the result.\n" + \
                       'Please write down the assertion and provide a short explaination. You should keep your answer within 200 words.'
        return instruction
        pass

    def _construct_instruction_all_in_one_for_assertBoolean(self, focal_method: str, test_prefix: str,
                                                            retrieved_focal_method: str | None,
                                                            retrieved_test_case: str | None) -> str:
        instruction = "Your task is to help me add an assertion to help me verify the correctness of a method under testing. The method is \n```java\n" + \
                      focal_method + "\n```\n Here is the test case for the above method: \n```java\n" + \
                      test_prefix + "\n```\n"
        instruction += "Now I need your help on writing one assertion at the `<AssertionPlaceHolder>` line, following the code comment in the test case."
        if retrieved_focal_method and retrieved_test_case:
            instruction += 'Here is a similar focal method and its corresponding test case, I hope this could help you:\n```java\n' + \
                           retrieved_focal_method + '\n' + retrieved_test_case + '\n```\n'
        instruction += 'Please read my code and write an assertion statement in the `<AssertionPlaceHolder>` line.\n' + \
                       "Note that you **MUST** use either `assertTrue()` or `assertFalse()` method to verify the result.\n" + \
                       'Please write down the assertion and provide a short explaination. You should keep your answer within 200 words.'
        return instruction
        pass

    def _construct_instruction_all_in_one_for_assertNullValue(self, focal_method: str, test_prefix: str,
                                                              retrieved_focal_method: str | None,
                                                              retrieved_test_case: str | None) -> str:
        instruction = "Your task is to help me add an assertion to help me verify the correctness of a method under testing. The method is \n```java\n" + \
                      focal_method + "\n```\n Here is the test case for the above method: \n```java\n" + \
                      test_prefix + "\n```\n"
        instruction += "Now I need your help on writing one assertion at the `<AssertionPlaceHolder>` line, following the code comment in the test case."
        if retrieved_focal_method and retrieved_test_case:
            instruction += 'Here is a similar focal method and its corresponding test case, I hope this could help you:\n```java\n' + \
                           retrieved_focal_method + '\n' + retrieved_test_case + '\n```\n'
        instruction += 'Please read my code and write an assertion statement in the `<AssertionPlaceHolder>` line.\n' + \
                       "Note that you **MUST** use either `assertNull()` or `assertNotNull()` method to verify the result.\n" + \
                       'Please write down the assertion and provide a short explaination. You should keep your answer within 200 words.'
        return instruction
        pass

    def _group_messages(self, retrieved_focal_method: str, retrieved_test_prefix: str, retrieved_ground_truth: str,
                        focal_method: str, test_prefix: str, allow_explain: bool) -> list:
        retrieved_instruction = self._construct_instruction(
            retrieved_focal_method, retrieved_test_prefix)
        target_instruction = self._construct_instruction(
            focal_method, test_prefix)
        messages = []
        messages.append({
            'role': 'system',
            'content': self.system_prompt
        })
        messages.append({
            'role': 'user',
            'content': retrieved_instruction
        })
        messages.append({
            'role': 'assistant',
            'content': f"```java\n{retrieved_ground_truth}\n```\n"
        })
        messages.append({
            'role': 'user',
            'content': target_instruction
        })
        return messages

    def _group_messages_v2(self, retrieved_focal_method: str, retrieved_test_case: str, focal_method: str,
                           test_prefix: str) -> list:
        retrieved_instruction = self._construct_instruction_all_in_one(
            focal_method=focal_method,
            test_prefix=test_prefix,
            retrieved_focal_method=retrieved_focal_method,
            retrieved_test_case=retrieved_test_case)
        messages = []
        messages.append({
            'role': 'system',
            'content': self.system_prompt
        })
        messages.append({
            'role': 'user',
            'content': retrieved_instruction
        })
        return messages

    def _group_messages_v2_with_code_features(self, retrieved_focal_method: str, retrieved_test_case: str,
                                              focal_method: str,
                                              test_prefix: str, focal_class_fields, focal_class_methods,
                                              test_class_fields,
                                              actual_value: str) -> list:
        retrieved_instruction = self._construct_instruction_all_in_one_with_code_feature(
            focal_method=focal_method,
            test_prefix=test_prefix,
            retrieved_focal_method=retrieved_focal_method,
            retrieved_test_case=retrieved_test_case,
            focal_class_fields=focal_class_fields,
            focal_class_methods=focal_class_methods,
            test_class_fields=test_class_fields,
            actual_value=actual_value
        )
        messages = []
        messages.append({
            'role': 'system',
            'content': self.system_prompt
        })
        messages.append({
            'role': 'user',
            'content': retrieved_instruction
        })
        return messages

    def _group_messages_v2_for_assertBool(self, retrieved_focal_method: str, retrieved_test_case: str,
                                          focal_method: str,
                                          test_prefix: str) -> list:
        retrieved_instruction = self._construct_instruction_all_in_one_for_assertBool(
            focal_method=focal_method,
            test_prefix=test_prefix,
            retrieved_focal_method=retrieved_focal_method,
            retrieved_test_case=retrieved_test_case)
        messages = []
        messages.append({
            'role': 'system',
            'content': self.system_prompt
        })
        messages.append({
            'role': 'user',
            'content': retrieved_instruction
        })
        return messages

    def _group_messages_v2_for_assertNullValue(self, retrieved_focal_method: str, retrieved_test_case: str,
                                               focal_method: str,
                                               test_prefix: str) -> list:
        retrieved_instruction = self._construct_instruction_all_in_one_for_assertNullValue(
            focal_method=focal_method,
            test_prefix=test_prefix,
            retrieved_focal_method=retrieved_focal_method,
            retrieved_test_case=retrieved_test_case)
        messages = []
        messages.append({
            'role': 'system',
            'content': self.system_prompt
        })
        messages.append({
            'role': 'user',
            'content': retrieved_instruction
        })
        return messages

    def refine(self, **kwargs) -> str:
        try:
            assert 'judge_response' in kwargs
        except AssertionError:
            logger.error('Missing required arguments: judge_response')
            exit(-1)
        judge_response = kwargs['judge_response']
        # First round: Understand the intention of the focal method
        messages = self.history
        messages.append({
            'role': 'user',
            'content': f"Now you are working with other colleagues to write proper assertion for the given method. Your codename is `NaiveGenerator`.\n"
                       f"Now, you and others have different answers, and your superior have commented on your answers.\n"
                       f"Please refine your previous answer according to his comment:\n\n{judge_response}\n\n"
                       f"Please write your answer in a code block and do not provide any explanation."
        })
        response = self.model.get_response(messages=messages)
        self._history = pickle.loads(pickle.dumps(messages))
        self._record_history('assistant', response)
        return response

    def generate_assertEquals(self, **kwargs):
        focal_method = kwargs['focal_method']
        test_prefix = kwargs['test_prefix']
        actual_value = kwargs['actual_value']
        retrieved_focal_method = """
                @Override
                public void setConfiguration (Configuration cfg)
                    throws ConfigurationException
                {
                    try {
                        String log_priority = cfg.get("priority");
                        if ( log_priority != null && !log_priority.trim().equals("") && LEVELS.containsKey(log_priority) ) {
                            priority = log_priority;
                        }
                    } catch (Exception e) {
                        throw new ConfigurationException (e);
                    }
                }
                """
        retrieved_test_case = """
                            @Test
                            public void testSetConfiguration() throws Throwable {
                                FilterLogListener filterLogListener = new FilterLogListener();
                                Configuration cfg = new SimpleConfiguration();
                                filterLogListener.setConfiguration(cfg);
                                assertEquals("filterLogListener.getPriority()", filterLogListener.getPriority());
                            }
                            """
        if kwargs['retrieved_focal_method'] and kwargs['retrieved_test_case']:
            retrieved_focal_method = kwargs['retrieved_focal_method']
            retrieved_test_case = kwargs['retrieved_test_case']

        # messages = self._group_messages_v2(retrieved_focal_method=retrieved_focal_method,
        #                                    retrieved_test_case=retrieved_test_case,
        #                                    focal_method=focal_method,
        #                                    test_prefix=test_prefix)
        messages = self._group_messages_v2_with_code_features(retrieved_focal_method=retrieved_focal_method,
                                                              retrieved_test_case=retrieved_test_case,
                                                              focal_method=focal_method,
                                                              test_prefix=test_prefix,
                                                              focal_class_fields=kwargs['focal_class_fields'],
                                                              focal_class_methods=kwargs['focal_class_methods'],
                                                              test_class_fields=kwargs['test_class_fields'],
                                                              actual_value=kwargs['actual_value']
                                                              )
        # response = self.model.get_response_with_prefix(
        #     messages, prefix=f'I think the answer should be:\n```java\nassertEquals(')
        response = self.model.get_response(messages=messages)
        self._history = pickle.loads(pickle.dumps(messages))
        self._record_history('assistant', response)
        return response

    def generate_assertBoolean(self, **kwargs):
        focal_method = kwargs['focal_method']
        test_prefix = kwargs['test_prefix']
        retrieved_focal_method = """
                @Override
                public void setConfiguration (Configuration cfg)
                    throws ConfigurationException
                {
                    try {
                        String log_priority = cfg.get("priority");
                        if ( log_priority != null && !log_priority.trim().equals("") && LEVELS.containsKey(log_priority) ) {
                            priority = log_priority;
                        }
                    } catch (Exception e) {
                        throw new ConfigurationException (e);
                    }
                }
                """
        retrieved_test_case = """
                            @Test
                            public void testSetConfiguration() throws Throwable {
                                FilterLogListener filterLogListener = new FilterLogListener();
                                Configuration cfg = new SimpleConfiguration();
                                filterLogListener.setConfiguration(cfg);
                                assertEquals("filterLogListener.getPriority()", filterLogListener.getPriority());
                            }
                            """
        if kwargs['retrieved_focal_method'] and kwargs['retrieved_test_case']:
            retrieved_focal_method = kwargs['retrieved_focal_method']
            retrieved_test_case = kwargs['retrieved_test_case']

        messages = self._group_messages_v2_for_assertBool(retrieved_focal_method=retrieved_focal_method,
                                                          retrieved_test_case=retrieved_test_case,
                                                          focal_method=focal_method,
                                                          test_prefix=test_prefix)
        # response = self.model.get_response_with_prefix(
        #     messages, prefix='I think the answer should be:\n```java\nassert')
        response = self.model.get_response(messages=messages)
        self._history = pickle.loads(pickle.dumps(messages))
        self._record_history('assistant', response)
        return response

    def generate_assertNullValue(self, **kwargs):
        focal_method = kwargs['focal_method']
        test_prefix = kwargs['test_prefix']
        retrieved_focal_method = """
                @Override
                public void setConfiguration (Configuration cfg)
                    throws ConfigurationException
                {
                    try {
                        String log_priority = cfg.get("priority");
                        if ( log_priority != null && !log_priority.trim().equals("") && LEVELS.containsKey(log_priority) ) {
                            priority = log_priority;
                        }
                    } catch (Exception e) {
                        throw new ConfigurationException (e);
                    }
                }
                """
        retrieved_test_case = """
                            @Test
                            public void testSetConfiguration() throws Throwable {
                                FilterLogListener filterLogListener = new FilterLogListener();
                                Configuration cfg = new SimpleConfiguration();
                                filterLogListener.setConfiguration(cfg);
                                assertEquals("filterLogListener.getPriority()", filterLogListener.getPriority());
                            }
                            """
        if kwargs['retrieved_focal_method'] and kwargs['retrieved_test_case']:
            retrieved_focal_method = kwargs['retrieved_focal_method']
            retrieved_test_case = kwargs['retrieved_test_case']

        messages = self._group_messages_v2_for_assertNullValue(retrieved_focal_method=retrieved_focal_method,
                                                               retrieved_test_case=retrieved_test_case,
                                                               focal_method=focal_method,
                                                               test_prefix=test_prefix)
        # response = self.model.get_response_with_prefix(
        #     messages, prefix='I think the answer should be:\n```java\nassert')
        response = self.model.get_response(messages=messages)
        self._history = pickle.loads(pickle.dumps(messages))
        self._record_history('assistant', response)
        return response

    def generate_assertEquals_multiple(self, **kwargs):
        focal_method = kwargs['focal_method']
        test_prefix = kwargs['test_prefix']
        actual_value = kwargs['actual_value']
        retrieved_focal_method = """
                @Override
                public void setConfiguration (Configuration cfg)
                    throws ConfigurationException
                {
                    try {
                        String log_priority = cfg.get("priority");
                        if ( log_priority != null && !log_priority.trim().equals("") && LEVELS.containsKey(log_priority) ) {
                            priority = log_priority;
                        }
                    } catch (Exception e) {
                        throw new ConfigurationException (e);
                    }
                }
                """
        retrieved_test_case = """
                            @Test
                            public void testSetConfiguration() throws Throwable {
                                FilterLogListener filterLogListener = new FilterLogListener();
                                Configuration cfg = new SimpleConfiguration();
                                filterLogListener.setConfiguration(cfg);
                                assertEquals("filterLogListener.getPriority()", filterLogListener.getPriority());
                            }
                            """
        if kwargs['retrieved_focal_method'] and kwargs['retrieved_test_case']:
            retrieved_focal_method = kwargs['retrieved_focal_method']
            retrieved_test_case = kwargs['retrieved_test_case']

        # messages = self._group_messages_v2(retrieved_focal_method=retrieved_focal_method,
        #                                    retrieved_test_case=retrieved_test_case,
        #                                    focal_method=focal_method,
        #                                    test_prefix=test_prefix)
        messages = self._group_messages_v2_with_code_features(retrieved_focal_method=retrieved_focal_method,
                                                              retrieved_test_case=retrieved_test_case,
                                                              focal_method=focal_method,
                                                              test_prefix=test_prefix,
                                                              focal_class_fields=kwargs['focal_class_fields'],
                                                              focal_class_methods=kwargs['focal_class_methods'],
                                                              test_class_fields=kwargs['test_class_fields'],
                                                              actual_value=kwargs['actual_value']
                                                              )
        responses, probs = self.model.get_multiple_responses_with_prefix(
            messages, prefix=f'I think the assertion should be:\n```java\nassertEquals(')
        self._history = pickle.loads(pickle.dumps(messages))
        return responses, probs

    def generate_assertBoolean_multiple(self, **kwargs):
        focal_method = kwargs['focal_method']
        test_prefix = kwargs['test_prefix']
        retrieved_focal_method = """
                @Override
                public void setConfiguration (Configuration cfg)
                    throws ConfigurationException
                {
                    try {
                        String log_priority = cfg.get("priority");
                        if ( log_priority != null && !log_priority.trim().equals("") && LEVELS.containsKey(log_priority) ) {
                            priority = log_priority;
                        }
                    } catch (Exception e) {
                        throw new ConfigurationException (e);
                    }
                }
                """
        retrieved_test_case = """
                            @Test
                            public void testSetConfiguration() throws Throwable {
                                FilterLogListener filterLogListener = new FilterLogListener();
                                Configuration cfg = new SimpleConfiguration();
                                filterLogListener.setConfiguration(cfg);
                                assertEquals("filterLogListener.getPriority()", filterLogListener.getPriority());
                            }
                            """
        if kwargs['retrieved_focal_method'] and kwargs['retrieved_test_case']:
            retrieved_focal_method = kwargs['retrieved_focal_method']
            retrieved_test_case = kwargs['retrieved_test_case']

        messages = self._group_messages_v2_for_assertBool(retrieved_focal_method=retrieved_focal_method,
                                                          retrieved_test_case=retrieved_test_case,
                                                          focal_method=focal_method,
                                                          test_prefix=test_prefix)
        responses, probs = self.model.get_multiple_responses_with_prefix(
            messages, prefix='I think the assertion should be:\n```java\nassert')
        # response = self.model.get_response(messages=messages)
        self._history = pickle.loads(pickle.dumps(messages))
        # self._record_history('assistant', response)
        return responses, probs

    def generate_assertNullValue_multiple(self, **kwargs):
        focal_method = kwargs['focal_method']
        test_prefix = kwargs['test_prefix']
        retrieved_focal_method = """
                @Override
                public void setConfiguration (Configuration cfg)
                    throws ConfigurationException
                {
                    try {
                        String log_priority = cfg.get("priority");
                        if ( log_priority != null && !log_priority.trim().equals("") && LEVELS.containsKey(log_priority) ) {
                            priority = log_priority;
                        }
                    } catch (Exception e) {
                        throw new ConfigurationException (e);
                    }
                }
                """
        retrieved_test_case = """
                            @Test
                            public void testSetConfiguration() throws Throwable {
                                FilterLogListener filterLogListener = new FilterLogListener();
                                Configuration cfg = new SimpleConfiguration();
                                filterLogListener.setConfiguration(cfg);
                                assertEquals("filterLogListener.getPriority()", filterLogListener.getPriority());
                            }
                            """
        if kwargs['retrieved_focal_method'] and kwargs['retrieved_test_case']:
            retrieved_focal_method = kwargs['retrieved_focal_method']
            retrieved_test_case = kwargs['retrieved_test_case']

        messages = self._group_messages_v2_for_assertNullValue(retrieved_focal_method=retrieved_focal_method,
                                                               retrieved_test_case=retrieved_test_case,
                                                               focal_method=focal_method,
                                                               test_prefix=test_prefix)
        responses, probs = self.model.get_multiple_responses_with_prefix(
            messages, prefix='I think the assertion should be:\n```java\nassert')
        self._history = pickle.loads(pickle.dumps(messages))
        # self._record_history('assistant', response)
        return responses, probs


class BaselineRAGGenerator(Generator):
    def __init__(self, model: LLM):
        self.system_prompt = "You are an expert in software testing, with 10 years of experience. You are very good at writing test cases."
        debate_system_prompt = (
            "You are an expert in software testing, with 10 years of experience. You are very good at writing test cases. "
            "Now you are user1 in a round table debate of three users. "
            "The debate is about choosing a more accurate expected value for an assertion statement. "
            "The opinions of the other two users are not always true, you can ignore any incorrect part of their opinion. "
            "And you can refer to their opinions to revise yours or defend your own. "
            "Please remember there should and must be a more plausible answer in the responses.")
        super().__init__(model, debate_system_prompt)
        self.understanding_history = []
        pass

    def construct_generation_messages(self, understanding, focal_method, test_prefix, retrieved_test_case):
        messages = []
        prompt = f"I want you to generate a Junit assertion for a test. Here is a brief introduction of the functionality of the method under test:\n{understanding}\n"
        prompt += f"\nNow, given test prefix <TEST> and focal method <FOCAL>. generate a Junit assertion:\n<TEST>:\n```\n{test_prefix}\n```\n<FOCAL>:\n```\n{focal_method}\n```\n"
        prompt += f"\nHere are some examples that you can follow when generating the best assert statement:\n```\n{retrieved_test_case}\n```\nPlease write **ONE** assertion to fit the `<Assertion_PlaceHolder>` line. Do not write a method or class for the assertion."
        messages.append({'role': 'user', 'content': prompt})
        return messages

    def construct_understanding_messages(self, focal_method, test_prefix):
        messages = []
        user_init_prompt = f"I will ask you to explain a few methods and classes. I will also walk you through the steps of a Java test method prefix and ask you about updates to each variable.\n"
        llm_init_response = f'Yes, I will try to understand and describe the method, classes and variable assignments that you provide.'
        messages.append(
            {'role': 'user', 'content': user_init_prompt}
        )
        messages.append(
            {'role': 'assistant', 'content': llm_init_response}
        )
        user_understanding_prompt = f'I have a method to test, can you explain this method? Here is the code\n```\n{focal_method}\n```\n'

        messages.append(
            {'role': 'user', 'content': user_understanding_prompt}
        )
        start = time.time()
        llm_secondary_response = self.model.get_response(messages)
        end = time.time()
        print(f"Time cost 1: {end - start}")
        messages.append({'role': 'assistant', 'content': llm_secondary_response})
        user_understanding_prompt = f'I have a test case that aims to test the aforementioned method, can you explain this test case? Here is the code\n```\n{test_prefix}\n```\n'

        messages.append(
            {'role': 'user', 'content': user_understanding_prompt}
        )
        start = time.time()
        llm_secondary_response = self.model.get_response(messages)
        end = time.time()
        print(f"Time cost 2: {end - start}")
        messages.append({'role': 'assistant', 'content': llm_secondary_response})
        return messages

    def generate(self, **kwargs):
        dialog = self.construct_understanding_messages(kwargs['focal_method'], kwargs['test_prefix'])
        understanding = '\n'.join([chat['content'] for chat in dialog[2:] if chat['role'] == 'assistant'])
        history = self.construct_generation_messages(understanding, kwargs['focal_method'], kwargs['test_prefix'],
                                                     kwargs['retrieved_test_case'])
        self.understanding_history = pickle.loads(pickle.dumps(dialog))
        start = time.time()
        response = self.model.get_response(history)
        end = time.time()
        print(f"Time cost 3: {end - start}")
        history.append({'role': 'assistant', 'content': response})
        self.update_history(history)
        return response

    def generate_assertEquals(self, **kwargs):
        pass

    def generate_assertNullValue(self, **kwargs):
        pass

    def generate_assertBoolean(self, **kwargs):
        pass

    def refine(self, **kwagrs):
        pass


class NaiveGenerator(Generator):
    def __init__(self, model: LLM):
        debate_system_prompt = (
            "You are an expert in software testing, with 10 years of experience. You are very good at writing test cases. "
            "Now you are user2 in a round table debate of three users. "
            "The debate is about choosing a more accurate expected value for an assertion statement. "
            "The opinions of the other two users are not always true, you can ignore any incorrect part of their opinion. "
            "And you can refer to their opinions to revise yours or defend your own. "
            "Please remember there should and must be a more plausible answer in the responses.")
        super().__init__(model, debate_system_prompt)
        self.system_prompt = "You are an expert in software testing, with 10 years of experience. You are very good at writing test cases."
        pass

    def _construct_instruction(self, focal_method: str, test_prefix: str, expected_value_type: str | None) -> str:
        instruction = 'Your task is to complete the given test case. The method under testing is \n```java\n' + \
                      focal_method + '\n```\n Here is part of the test case for the above method: \n```java\n' + \
                      test_prefix + '\n```\n'
        instruction += 'Please read the code, and accomplish the assertion statement by choosing the proper value for the `<expected_value>` part.\n'
        # instruction += "Please directly respond the code without any explanation."
        if expected_value_type and self.type_to_predefined_candidates(expected_value_type):
            if expected_value_type == 'boolean':
                instruction += f"You must use **ONE BOOLEAN VALUE** (i.e., true or false) to fill the `<expected_value>` part."
                pass
            else:
                instruction += f"Here are some possible values of according to the type of the expected value: `{self.type_to_predefined_candidates(expected_value_type)}`."
        instruction += "\nPlease write down the completed assertion and provide a short explaination. You should keep your answer within 200 words. "
        return instruction
        pass

    def _construct_instruction_for_assertBoolean(self, focal_method: str, test_prefix: str,
                                                 expected_value_type: str | None) -> str:
        instruction = 'Your task is to complete the given test case. The method under testing is \n```java\n' + \
                      focal_method + '\n```\n Here is part of the test case for the above method: \n```java\n' + \
                      test_prefix + '\n```\n'
        instruction += 'Please read my code and write an assertion statement in the `<AssertionPlaceHolder>` line.\n' + \
                       "You **MUST** use either `assertTrue()` or `assertFalse()` method to verify the result.\n" + \
                       'Please write down the assertion and provide a short explaination. You should keep your answer within 200 words.'
        return instruction
        pass

    def _construct_instruction_with_code_features(self, focal_method: str, test_prefix: str, focal_class_fields: list,
                                                  focal_class_methods: list, test_class_fields: list,
                                                  actual_value) -> str:
        instruction = 'Your task is to complete the given test case. The method under testing is \n```java\n' + \
                      focal_method + '\n```\n'
        if len(focal_class_fields) != 0 or len(focal_class_methods) != 0:
            instruction += 'The method is declared in a class with the following fields and methods:\n```java\n'
            if len(focal_class_fields) != 0:
                instruction += '//Defined fields'
                for field in focal_class_fields:
                    instruction += field + '\n'
            if len(focal_class_methods) != 0:
                instruction += '//Defined methods'
                for method in focal_class_methods:
                    instruction += method + '\n'
                instruction += '```\n'

        if len(test_class_fields) != 0:
            instruction += 'The test case is declared in a class with the following fields:\n```java\n'
            for field in test_class_fields:
                instruction += field + '\n'
            instruction += '```\n'
        instruction += 'Here is part of the test case for the method under testing: \n```java\n' + \
                       test_prefix + '\n```\n'
        instruction += 'Please read the given code features (i.e., fields and methods) and the test case, and determine what should we place in the <expected_value> part of the assertion.\n'
        instruction += "Please directly respond the code without any explanation."
        return instruction

    def _construct_instruction_with_code_features_for_assertBoolean(self, focal_method: str, test_prefix: str,
                                                                    focal_class_fields: list,
                                                                    focal_class_methods: list,
                                                                    test_class_fields: list) -> str:
        instruction = 'Your task is to complete the given test case. The method under testing is \n```java\n' + \
                      focal_method + '\n```\n'
        if len(focal_class_fields) != 0 or len(focal_class_methods) != 0:
            instruction += 'The method is declared in a class with the following fields and methods:\n```java\n'
            if len(focal_class_fields) != 0:
                instruction += '//Defined fields'
                for field in focal_class_fields:
                    instruction += field + '\n'
            if len(focal_class_methods) != 0:
                instruction += '//Defined methods'
                for method in focal_class_methods:
                    instruction += method + '\n'
                instruction += '```\n'

        if len(test_class_fields) != 0:
            instruction += 'The test case is declared in a class with the following fields:\n```java\n'
            for field in test_class_fields:
                instruction += field + '\n'
            instruction += '```\n'
        instruction += 'Here is part of the test case for the method under testing: \n```java\n' + \
                       test_prefix + '\n```\n'
        instruction += 'Please read my code and write an assertion statement in the `<AssertionPlaceHolder>` line.\n' + \
                       "Note that you **MUST** use either `assertTrue()` or `assertFalse()` method to verify the result.\n" + \
                       'Please write down the assertion and provide a short explaination. You should keep your answer within 200 words.'
        return instruction

    def _construct_instruction_for_assertNullValues(self, focal_method: str, test_prefix: str) -> str:
        instruction = 'Your task is to complete the given test case. The method under testing is \n```java\n' + \
                      focal_method + '\n```\n'
        instruction += 'Here is part of the test case for the method under testing: \n```java\n' + \
                       test_prefix + '\n```\n'
        instruction += 'Please read my code and write an assertion statement in the `<AssertionPlaceHolder>` line.\n' + \
                       "You **MUST** use either `assertNull()` or `assertNotNull()` method to verify the result.\n" + \
                       'Please write down the assertion and provide a short explanation. You should keep your answer within 200 words.'
        return instruction

    def _group_messages(self, focal_method: str, test_prefix: str, expected_value_type: str | None) -> list:
        instruction = self._construct_instruction(
            focal_method, test_prefix, expected_value_type)
        messages = []
        messages.append({
            'role': 'system',
            'content': self.system_prompt
        })
        messages.append({
            'role': 'user',
            'content': instruction
        })
        return messages

    def _group_messages_with_code_features(self, focal_method: str, test_prefix: str, focal_class_fields: list,
                                           focal_class_methods: list, test_class_fields: list,
                                           actual_value: str) -> list:
        instruction = self._construct_instruction_with_code_features(focal_method, test_prefix, focal_class_fields,
                                                                     focal_class_methods, test_class_fields,
                                                                     actual_value)
        messages = []
        messages.append({
            'role': 'system',
            'content': self.system_prompt
        })
        messages.append({
            'role': 'user',
            'content': instruction
        })
        return messages

    def _group_messages_for_assertNullValues(self, focal_method: str, test_prefix: str) -> list:
        instruction = self._construct_instruction_for_assertNullValues(
            focal_method, test_prefix)
        messages = []
        messages.append({
            'role': 'system',
            'content': self.system_prompt
        })
        messages.append({
            'role': 'user',
            'content': instruction
        })
        return messages

    def refine(self, **kwargs) -> str:
        try:
            assert 'judge_response' in kwargs
        except AssertionError:
            logger.error('Missing required arguments: judge_response')
            exit(-1)
        judge_response = kwargs['judge_response']
        # First round: Understand the intention of the focal method
        messages = self.history
        messages.append({
            'role': 'user',
            'content': f"Now you are working with other colleagues to write proper assertion for the given method. Your codename is `NaiveGenerator`.\n"
                       f"Now, you and others have different answers, and your superior have commented on your answers.\n"
                       f"Please refine your previous answer according to his comment:\n\n{judge_response}\n\n"
                       f"Please write your answer in a code block and do not provide any explanation."
        })
        response = self.model.get_response(messages=messages)
        self._history = pickle.loads(pickle.dumps(messages))
        self._record_history('assistant', response)
        return response

    def _group_messages_for_assertBoolean(self, focal_method: str, test_prefix: str,
                                          expected_value_type: str | None) -> list:
        instruction = self._construct_instruction_for_assertBoolean(
            focal_method, test_prefix, expected_value_type)
        messages = []
        messages.append({
            'role': 'system',
            'content': self.system_prompt
        })
        messages.append({
            'role': 'user',
            'content': instruction
        })
        return messages

    def generate_assertEquals(self, **kwargs) -> str:
        try:
            assert 'focal_method' in kwargs and 'test_prefix' in kwargs
            assert 'focal_class_fields' in kwargs and 'focal_class_methods' in kwargs and 'test_class_fields' in kwargs
        except AssertionError:
            logger.error(
                'Missing one or more required arguments: focal_method, test_prefix, focal_class_fields, focal_class_methods, or test_class_fields')
            exit(-1)
        focal_method = kwargs['focal_method']
        test_prefix = kwargs['test_prefix']
        focal_class_fields = kwargs['focal_class_fields']
        focal_class_methods = kwargs['focal_class_methods']
        test_class_fields = kwargs['test_class_fields']
        actual_value = kwargs['actual_value']
        messages = self._group_messages_with_code_features(focal_method, test_prefix, focal_class_fields,
                                                           focal_class_methods, test_class_fields,
                                                           actual_value=kwargs['actual_value'])
        # response = self.model.get_response_with_prefix(
        #     messages, prefix=f'I think the answer should be:\n```java\nassertEquals(')
        response = self.model.get_response(messages=messages)
        self._history = pickle.loads(pickle.dumps(messages))
        self._record_history('assistant', response)
        return response

    def generate_assertBoolean(self, **kwargs):
        try:
            assert 'focal_method' in kwargs and 'test_prefix' in kwargs
            assert 'focal_class_fields' in kwargs and 'focal_class_methods' in kwargs and 'test_class_fields' in kwargs
        except AssertionError:
            logger.error(
                'Missing one or more required arguments: focal_method, test_prefix, focal_class_fields, focal_class_methods, or test_class_fields')
            exit(-1)
        focal_method = kwargs['focal_method']
        test_prefix = kwargs['test_prefix']
        if 'expected_value_type' in kwargs:
            expected_value_type = kwargs['expected_value_type']
        else:
            expected_value_type = None
        # messages = self._group_messages_with_code_features(focal_method, test_prefix, kwargs['focal_class_fields'],
        #                                                    kwargs['focal_class_methods'], kwargs['test_class_fields'])
        messages = self._group_messages_for_assertBoolean(
            focal_method, test_prefix, expected_value_type)

        # response = self.model.get_response_with_prefix(
        #     messages, prefix='I think the answer should be:\n```java\nassert')
        response = self.model.get_response(messages=messages)
        self._history = pickle.loads(pickle.dumps(messages))
        self._record_history('assistant', response)
        return response

    def generate_assertNullValue(self, **kwargs):
        try:
            assert 'focal_method' in kwargs and 'test_prefix' in kwargs
            assert 'focal_class_fields' in kwargs and 'focal_class_methods' in kwargs and 'test_class_fields' in kwargs
        except AssertionError:
            logger.error(
                'Missing one or more required arguments: focal_method, test_prefix, focal_class_fields, focal_class_methods, or test_class_fields')
            exit(-1)
        focal_method = kwargs['focal_method']
        test_prefix = kwargs['test_prefix']

        # messages = self._group_messages_with_code_features(focal_method, test_prefix, kwargs['focal_class_fields'],
        #                                                    kwargs['focal_class_methods'], kwargs['test_class_fields'])
        messages = self._group_messages_for_assertNullValues(
            focal_method, test_prefix)

        # response = self.model.get_response_with_prefix(
        #     messages, prefix='I think the answer should be:\n```java\nassert')
        response = self.model.get_response(messages=messages)
        self._history = pickle.loads(pickle.dumps(messages))
        self._record_history('assistant', response)
        return response

    def generate_assertEquals_multiple(self, **kwargs) -> str:
        try:
            assert 'focal_method' in kwargs and 'test_prefix' in kwargs
            assert 'focal_class_fields' in kwargs and 'focal_class_methods' in kwargs and 'test_class_fields' in kwargs
        except AssertionError:
            logger.error(
                'Missing one or more required arguments: focal_method, test_prefix, focal_class_fields, focal_class_methods, or test_class_fields')
            exit(-1)
        focal_method = kwargs['focal_method']
        test_prefix = kwargs['test_prefix']
        focal_class_fields = kwargs['focal_class_fields']
        focal_class_methods = kwargs['focal_class_methods']
        test_class_fields = kwargs['test_class_fields']
        actual_value = kwargs['actual_value']
        messages = self._group_messages_with_code_features(focal_method, test_prefix, focal_class_fields,
                                                           focal_class_methods, test_class_fields,
                                                           actual_value=kwargs['actual_value'])
        responses, probs = self.model.get_multiple_responses_with_prefix(
            messages, prefix=f'I think the assertion should be:\n```java\nassertEquals(')
        # response = self.model.get_response(messages=messages)
        self._history = pickle.loads(pickle.dumps(messages))
        # self._record_history('assistant', response)
        return responses, probs

    def generate_assertBoolean_multiple(self, **kwargs):
        try:
            assert 'focal_method' in kwargs and 'test_prefix' in kwargs
            assert 'focal_class_fields' in kwargs and 'focal_class_methods' in kwargs and 'test_class_fields' in kwargs
        except AssertionError:
            logger.error(
                'Missing one or more required arguments: focal_method, test_prefix, focal_class_fields, focal_class_methods, or test_class_fields')
            exit(-1)
        focal_method = kwargs['focal_method']
        test_prefix = kwargs['test_prefix']
        if 'expected_value_type' in kwargs:
            expected_value_type = kwargs['expected_value_type']
        else:
            expected_value_type = None
        # messages = self._group_messages_with_code_features(focal_method, test_prefix, kwargs['focal_class_fields'],
        #                                                    kwargs['focal_class_methods'], kwargs['test_class_fields'])
        messages = self._group_messages_for_assertBoolean(
            focal_method, test_prefix, expected_value_type)

        responses, probs = self.model.get_multiple_responses_with_prefix(
            messages, prefix='I think the assertion should be:\n```java\nassert')
        # response = self.model.get_response(messages=messages)
        self._history = pickle.loads(pickle.dumps(messages))
        # self._record_history('assistant', response)
        return responses, probs

    def generate_assertNullValue_multiple(self, **kwargs):
        try:
            assert 'focal_method' in kwargs and 'test_prefix' in kwargs
            assert 'focal_class_fields' in kwargs and 'focal_class_methods' in kwargs and 'test_class_fields' in kwargs
        except AssertionError:
            logger.error(
                'Missing one or more required arguments: focal_method, test_prefix, focal_class_fields, focal_class_methods, or test_class_fields')
            exit(-1)
        focal_method = kwargs['focal_method']
        test_prefix = kwargs['test_prefix']

        # messages = self._group_messages_with_code_features(focal_method, test_prefix, kwargs['focal_class_fields'],
        #                                                    kwargs['focal_class_methods'], kwargs['test_class_fields'])
        messages = self._group_messages_for_assertNullValues(
            focal_method, test_prefix)

        responses, probs = self.model.get_multiple_responses_with_prefix(
            messages, prefix='I think the assertion should be:\n```java\nassert')
        self._history = pickle.loads(pickle.dumps(messages))
        return responses, probs


class FourStepCoTGenerator(Generator):
    def __init__(self, model):
        debate_system_prompt = (
            "You are an expert in software testing, with 10 years of experience. You are very good at writing test cases. "
            "Now you are user3 in a round table debate of three users. "
            "The debate is about choosing a more accurate expected value for an assertion statement. "
            "The opinions of the other two users are not always true, you can ignore any incorrect part of their opinion. "
            "And you can refer to their opinions to revise yours or defend your own. "
            "Please remember there should and must be a more plausible answer in the responses.")
        super().__init__(model, debate_system_prompt)
        self.system_prompt = "You are an expert in software testing, with 10 years of experience. You are very good at writing test cases. You must give short and concise answers."

    def first_round_messages(self, focal_method_name, focal_method, test_prefix):
        messages = [{
            'role': 'system',
            'content': self.system_prompt
        }, {
            'role': 'user',
            'content': f'I have a test case for a method named`{focal_method_name}`:\n```java\n{test_prefix}\n```\n'
                       f'Please read the test case, and tell me what scenario does this test case cover.'
            #    f'Please read the test case, and find out the input values in the test case for the `{focal_method_name}`.'
        }]
        self.update_history(messages)
        return messages

    def second_round_messages(self, focal_method_name, focal_method, test_prefix):
        new_messages = pickle.loads(pickle.dumps(self._history))
        new_messages.append({
            'role': 'user',
            'content': f'Here is the code of `{focal_method_name}` method:\n```java\n{focal_method}\n```\n'
                       f'Please read the code, and analyze the execution path of the `{focal_method_name}` method when given the input values.'
        })
        self.update_history(new_messages)
        return new_messages

    def third_round_messages(self, focal_method_name, focal_method, test_prefix):
        new_messages = pickle.loads(pickle.dumps(self._history))
        new_messages.append({
            'role': 'user',
            'content': f'According to your analysis, what is the output of the `{focal_method_name}` method under the given inputs?'
        })
        self.update_history(new_messages)
        return new_messages

    def final_round_messages(self, focal_method_name, focal_method, test_prefix, expected_value_type: str | None,
                             actual_value: str):
        new_messages = pickle.loads(pickle.dumps(self._history))
        instruction = f'Based on your analysis, please accomplish the given test case by filling proper value in the `<expected_value>` part:\n```java\n{test_prefix}\n```\n'
        instruction += "\nPlease write down the completed assertion and provide a short explaination. You should keep your answer within 200 words. "
        new_messages.append({
            'role': 'user',
            'content': instruction
        })
        self.update_history(new_messages)
        return new_messages

    def final_round_messages_with_code_features(self, focal_method_name, focal_method, test_prefix,
                                                expected_value_type: str | None, focal_class_fields,
                                                focal_class_methods, test_class_fields):
        new_messages = pickle.loads(pickle.dumps(self._history))
        instruction = f'Based on the outputs, please accomplish the given test case by filling proper value in the `<expected_value>` part:\n```java\n{test_prefix}\n```\n'
        if len(focal_class_fields) != 0 or len(focal_class_methods) != 0:
            instruction += 'The method is declared in a class with the following fields and methods:\n```java\n'
            if len(focal_class_fields) != 0:
                instruction += '//Defined fields'
                for field in focal_class_fields:
                    instruction += field + '\n'
            if len(focal_class_methods) != 0:
                instruction += '//Defined methods'
                for method in focal_class_methods:
                    instruction += method + '\n'
                instruction += '```\n'

        if len(test_class_fields) != 0:
            instruction += 'The test case is declared in a class with the following fields:\n```java\n'
            for field in test_class_fields:
                instruction += field + '\n'
            instruction += '```\n'

        if expected_value_type and self.type_to_predefined_candidates(expected_value_type):
            if expected_value_type == 'boolean':
                instruction += f"You must use **ONE BOOLEAN VALUE** (i.e., true or false) to fill the `<expected_value>` part."
                pass
            else:
                instruction += f"Here are some possible values of according to the type of the expected value: `{self.type_to_predefined_candidates(expected_value_type)}`."
        instruction += "\nPlease write down the completed assertion and provide a short explaination. You should keep your answer within 200 words. "
        new_messages.append({
            'role': 'user',
            'content': instruction
        })
        self.update_history(new_messages)
        return new_messages

    def final_round_messages_for_assertBoolean(self, focal_method_name, focal_method, test_prefix,
                                               expected_value_type: str | None):
        new_messages = pickle.loads(pickle.dumps(self._history))
        instruction = f'Based on your analysis, please accomplish the given test case by writing an assertion statement in the `<AssertionPlaceHolder>` line:\n```java\n{test_prefix}\n```\n'
        instruction += f"Please read my code and write an assertion statement in the `<AssertionPlaceHolder>` line." + \
                       "Note that you **MUST** use either `assertTrue()` or `assertFalse()` method to verify the result." + \
                       "Please write down the assertion and provide a short explaination. You should keep your answer within 200 words."
        new_messages.append({
            'role': 'user',
            'content': instruction
        })
        self.update_history(new_messages)
        return new_messages

    def final_round_messages_assertNullValues(self, focal_method_name, focal_method, test_prefix,
                                              expected_value_type: str | None):
        new_messages = pickle.loads(pickle.dumps(self._history))
        instruction = f'Based on your analysis, please accomplish the given test case by writing an assertion statement in the `<AssertionPlaceHolder>` line:\n```java\n{test_prefix}\n```\n'
        instruction += "Note that you **MUST** use either `assertNull()` or `assertNotNull()` method to verify the result." + \
                       "Please write down the assertion and provide a short explanation. You should keep your answer within 200 words."
        new_messages.append({
            'role': 'user',
            'content': instruction
        })
        self.update_history(new_messages)
        return new_messages

    def refine(self, **kwagrs):
        return ''

    def generate_assertEquals(self, **kwargs):
        try:
            assert 'focal_method' in kwargs and 'focal_method_name' in kwargs and 'test_prefix' in kwargs
        except AssertionError:
            logger.error(
                'Missing one or more parameters: focal_method, focal_method_name, and/or test_prefix')
            exit(1)
        focal_method_name = kwargs['focal_method_name']
        focal_method = kwargs['focal_method']
        test_prefix = kwargs['test_prefix']
        actual_value = kwargs['actual_value']
        expected_value_type = kwargs['expected_value_type'] if 'expected_value_type' in kwargs else None
        first_round_response = self.model.get_response(
            messages=self.first_round_messages(focal_method_name, focal_method, test_prefix))
        self._record_history(role='assistant', content=first_round_response)
        second_round_response = self.model.get_response(
            messages=self.second_round_messages(focal_method_name, focal_method, test_prefix))
        self._record_history(role='assistant', content=second_round_response)
        third_round_response = self.model.get_response(
            messages=self.third_round_messages(
                focal_method_name, focal_method, test_prefix)
        )
        self._record_history(role='assistant', content=third_round_response)
        # final_round_response = self.model.get_response_with_prefix(
        #     messages=self.final_round_messages(
        #         focal_method_name, focal_method, test_prefix, expected_value_type, actual_value=kwargs['actual_value']),
        #     prefix=f'I think the answer should be:\n```java\nassertEquals('
        # )
        final_round_response = self.model.get_response(messages=self.final_round_messages(
            focal_method_name, focal_method, test_prefix, expected_value_type, actual_value=kwargs['actual_value']))

        self._record_history(role='assistant', content=final_round_response)
        return final_round_response

    def generate_assertBoolean(self, **kwargs):
        try:
            assert 'focal_method' in kwargs and 'focal_method_name' in kwargs and 'test_prefix' in kwargs
        except AssertionError:
            logger.error(
                'Missing one or more parameters: focal_method, focal_method_name, and/or test_prefix')
            exit(1)
        focal_method_name = kwargs['focal_method_name']
        focal_method = kwargs['focal_method']
        test_prefix = kwargs['test_prefix']
        expected_value_type = kwargs['expected_value_type'] if 'expected_value_type' in kwargs else None
        first_round_response = self.model.get_response(
            messages=self.first_round_messages(focal_method_name, focal_method, test_prefix))
        self._record_history(role='assistant', content=first_round_response)
        second_round_response = self.model.get_response(
            messages=self.second_round_messages(focal_method_name, focal_method, test_prefix))
        self._record_history(role='assistant', content=second_round_response)
        third_round_response = self.model.get_response(
            messages=self.third_round_messages(
                focal_method_name, focal_method, test_prefix)
        )
        self._record_history(role='assistant', content=third_round_response)
        # final_round_response = self.model.get_response_with_prefix(
        #     messages=self.final_round_messages_for_assertBoolean(
        #         focal_method_name, focal_method, test_prefix, expected_value_type),
        #     prefix='I think the answer should be:\n```java\nassert'
        # )
        final_round_response = self.model.get_response(
            messages=self.final_round_messages_for_assertBoolean(focal_method_name, focal_method, test_prefix,
                                                                 expected_value_type))
        self._record_history(role='assistant', content=final_round_response)
        return final_round_response

    def generate_assertNullValue(self, **kwargs):
        try:
            assert 'focal_method' in kwargs and 'focal_method_name' in kwargs and 'test_prefix' in kwargs
        except AssertionError:
            logger.error(
                'Missing one or more parameters: focal_method, focal_method_name, and/or test_prefix')
            exit(1)
        focal_method_name = kwargs['focal_method_name']
        focal_method = kwargs['focal_method']
        test_prefix = kwargs['test_prefix']
        expected_value_type = kwargs['expected_value_type'] if 'expected_value_type' in kwargs else None
        first_round_response = self.model.get_response(
            messages=self.first_round_messages(focal_method_name, focal_method, test_prefix))
        self._record_history(role='assistant', content=first_round_response)
        second_round_response = self.model.get_response(
            messages=self.second_round_messages(focal_method_name, focal_method, test_prefix))
        self._record_history(role='assistant', content=second_round_response)
        third_round_response = self.model.get_response(
            messages=self.third_round_messages(
                focal_method_name, focal_method, test_prefix)
        )
        self._record_history(role='assistant', content=third_round_response)
        # final_round_response = self.model.get_response_with_prefix(
        #     messages=self.final_round_messages_assertNullValues(focal_method_name, focal_method, test_prefix,
        #                                                         expected_value_type),
        #     prefix='I think the answer should be:\n```java\nassert'
        # )
        final_round_response = self.model.get_response(
            messages=self.final_round_messages_assertNullValues(focal_method_name, focal_method, test_prefix,
                                                                expected_value_type))
        self._record_history(role='assistant', content=final_round_response)
        return final_round_response

    def generate_assertEquals_multiple(self, **kwargs):
        try:
            assert 'focal_method' in kwargs and 'focal_method_name' in kwargs and 'test_prefix' in kwargs
        except AssertionError:
            logger.error(
                'Missing one or more parameters: focal_method, focal_method_name, and/or test_prefix')
            exit(1)
        focal_method_name = kwargs['focal_method_name']
        focal_method = kwargs['focal_method']
        test_prefix = kwargs['test_prefix']
        actual_value = kwargs['actual_value']
        expected_value_type = kwargs['expected_value_type'] if 'expected_value_type' in kwargs else None
        first_round_response = self.model.get_response(
            messages=self.first_round_messages(focal_method_name, focal_method, test_prefix))
        self._record_history(role='assistant', content=first_round_response)
        second_round_response = self.model.get_response(
            messages=self.second_round_messages(focal_method_name, focal_method, test_prefix))
        self._record_history(role='assistant', content=second_round_response)
        third_round_response = self.model.get_response(
            messages=self.third_round_messages(
                focal_method_name, focal_method, test_prefix)
        )
        self._record_history(role='assistant', content=third_round_response)
        responses, probs = self.model.get_multiple_responses_with_prefix(
            messages=self.final_round_messages(
                focal_method_name, focal_method, test_prefix, expected_value_type, actual_value=kwargs['actual_value']),
            prefix=f'I think the assertion should be:\n```java\nassertEquals('
        )
        return responses, probs

    def generate_assertBoolean_multiple(self, **kwargs):
        try:
            assert 'focal_method' in kwargs and 'focal_method_name' in kwargs and 'test_prefix' in kwargs
        except AssertionError:
            logger.error(
                'Missing one or more parameters: focal_method, focal_method_name, and/or test_prefix')
            exit(1)
        focal_method_name = kwargs['focal_method_name']
        focal_method = kwargs['focal_method']
        test_prefix = kwargs['test_prefix']
        expected_value_type = kwargs['expected_value_type'] if 'expected_value_type' in kwargs else None
        first_round_response = self.model.get_response(
            messages=self.first_round_messages(focal_method_name, focal_method, test_prefix))
        self._record_history(role='assistant', content=first_round_response)
        second_round_response = self.model.get_response(
            messages=self.second_round_messages(focal_method_name, focal_method, test_prefix))
        self._record_history(role='assistant', content=second_round_response)
        third_round_response = self.model.get_response(
            messages=self.third_round_messages(
                focal_method_name, focal_method, test_prefix)
        )
        self._record_history(role='assistant', content=third_round_response)
        responses, probs = self.model.get_multiple_responses_with_prefix(
            messages=self.final_round_messages_for_assertBoolean(
                focal_method_name, focal_method, test_prefix, expected_value_type),
            prefix='I think the assertion should be:\n```java\nassert'
        )
        return responses, probs

    def generate_assertNullValue_multiple(self, **kwargs):
        try:
            assert 'focal_method' in kwargs and 'focal_method_name' in kwargs and 'test_prefix' in kwargs
        except AssertionError:
            logger.error(
                'Missing one or more parameters: focal_method, focal_method_name, and/or test_prefix')
            exit(1)
        focal_method_name = kwargs['focal_method_name']
        focal_method = kwargs['focal_method']
        test_prefix = kwargs['test_prefix']
        expected_value_type = kwargs['expected_value_type'] if 'expected_value_type' in kwargs else None
        first_round_response = self.model.get_response(
            messages=self.first_round_messages(focal_method_name, focal_method, test_prefix))
        self._record_history(role='assistant', content=first_round_response)
        second_round_response = self.model.get_response(
            messages=self.second_round_messages(focal_method_name, focal_method, test_prefix))
        self._record_history(role='assistant', content=second_round_response)
        third_round_response = self.model.get_response(
            messages=self.third_round_messages(
                focal_method_name, focal_method, test_prefix)
        )
        self._record_history(role='assistant', content=third_round_response)
        responses, probs = self.model.get_multiple_responses_with_prefix(
            messages=self.final_round_messages_assertNullValues(focal_method_name, focal_method, test_prefix,
                                                                expected_value_type),
            prefix='I think the assertion should be:\n```java\nassert'
        )
        return responses, probs

