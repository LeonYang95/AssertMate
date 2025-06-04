import sys
sys.path.extend(['.', '..'])
from llms import *
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
            'RAGGenerator': 'Alice',
            'NaiveGenerator': 'Bob',
            'FourStepCoTGenerator': 'Charlie'
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
    def generate_assertNullValue(self, **kwargs):
        pass

    @abstractmethod
    def generate_assertBoolean(self, **kwargs):
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

    def _group_debate_messages(self, focal_method: str, test_prefix: str, statements: dict,
                               expected_value: str) -> list:
        instruction = 'You and other teammates are asked to accomplish the following test case:\n```java\n' + test_prefix + '\n```\n'
        instruction += 'And the method under test is:\n```java\n' + focal_method + '\n```\n\n'
        instruction += 'Here are your answers:\n'
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
            f'\n\nNow you are in a debate with other users. Remember you are **{cur_user}**. What do you think about the opinions of {other_user_str}?'
            ' Please give your final answer of the assertion statement starting with “I think the answer should be” and explain very shortly starting with “Explanation: ”.')
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
        messages = self._group_debate_messages(
            focal_method=focal_method, test_prefix=test_prefix,
            statements=statements, expected_value=kwargs['expected_value'])
        # response = self.model.get_response_with_prefix(
        #     messages=messages,
        #     prefix='I think the answer should be:\n```java\nassertEquals(')
        response = self.model.get_response(messages)
        self._history = messages
        self._record_history(role='assistant', content=response)
        return response

    def debate_with_others(self, **kwargs):
        other_opinions = kwargs['other_opinions']
        response_prefix = kwargs['response_prefix']
        self_answer = kwargs['answer']
        messages = self.history

        if len(other_opinions) == 2:
            instruction = "Your colleagues have different opinions:\n"
            pass
        else:
            instruction = "Your colleague has a different opinion:\n"
            pass

        member_names = ""
        for role, statement in other_opinions.items():
            instruction += f"- {role}: {statement}\n"

        instruction += '\n'
        instruction += f'Remember, your answer is `{self_answer}`.'
        instruction += "Now I need one assertion that contains the correct expected value for the assertion. And you are going to debate with your colleagues.\n"
        instruction += "Let's think step by step:\n"
        instruction += f"- Please simulate the test case's execution, and gathering the results.\n"
        instruction += f"- Understand the differences between your answer and the opinion(s) from your colleague?\n"
        instruction += f"- Based on your analysis, what value do you think is more likely to help the test case pass without errors?\n"
        messages.append({
            'role': 'user',
            'content': instruction
        })
        response = self.model.get_response(messages)
        messages.append({
            'role': 'assistant',
            'content': response
        })
        messages.append({
            'role': 'user',
            'content': "OK, thanks for your comment. Now I need an complete assertion statement and an argument of why your answer is corect."
        })
        # response = self.model.get_response(messages)
        response = self.model.get_response_with_prefix(messages, prefix=response_prefix)
        self.update_history(messages)
        self._record_history('assistant', response)
        return response

    def debate_with_others_with_confidence(self, **kwargs):
        other_opinions = kwargs['other_opinions']
        other_probs = kwargs['other_probs']
        response_prefix = kwargs['response_prefix']
        self_answer = kwargs['answer']
        messages = self.history

        if len(other_opinions) == 2:
            instruction = "Your colleagues have different opinions:\n"
            pass
        else:
            instruction = "Your colleague has a different opinion:\n"
            pass

        member_names = ""
        for role, statement in other_opinions.items():
            instruction += f"- {role} (Confidence:{other_probs[role]}%): {statement}\n"

        instruction += '\n'
        instruction += f'Remember, your answer is `{self_answer}`.'
        instruction += "Now I need one assertion that contains the correct expected value for the assertion. And you are going to debate with your colleagues.\n"
        instruction += "Please note that the confidence level only means how confident they are about their answer, not the confidence level of the correctness. \nLet's think step by step:\n"
        instruction += f"- Check the actual value from the test case. Assertion that is targeting at a different actual value should not be considered.\n"
        instruction += f"- Findout the execution results of the actual value according to the test logic of the given test case.\n"
        instruction += f"- Based on your analysis and the answers from other colleagues, which assertion do you think is more likely to help the test case pass without errors?\n"
        messages.append({
            'role': 'user',
            'content': instruction
        })
        response = self.model.get_response(messages)
        messages.append({
            'role': 'assistant',
            'content': response
        })
        messages.append({
            'role': 'user',
            'content': "OK, thanks for your comment. Now I need an complete assertion statement and an argument of why your answer is corect."
        })
        # response = self.model.get_response(messages)
        responses, probs = self.model.get_multiple_responses_with_prefix(messages, prefix=response_prefix, best_of=5)

        # Select the one with the highest probs
        max_prob_idx = [index for index, prob in sorted(enumerate(probs), key=lambda x: x[1], reverse=True)][0]
        response = responses[max_prob_idx]
        prob = probs[max_prob_idx]
        self.update_history(messages[:-3])
        self._record_history('assistant', response)
        return response, prob

    def _construct_instruction_for_differential_based_refine(self, guide, expected_value) -> list:
        instruction = "Now you and your teammates have different opinions and your supervisor have given his advise on how to justify your answer."
        instruction += f'His advices are as follows:\n{guide}\n'
        instruction += f'Please read his advice and decide whether you need to change your answer. You can choose either hold onto your answer or change your answer if necessary. But there are some rules that you need to follow:\n'
        if expected_value in ['assertTrue', 'assertFalse']:
            instruction += f"- Either way, you **MUST** use `assertTrue` or `assertFalse` to check the result. You must give a **DIRECT PREDICTION** that is likely to pass execution based on your analysis and the advise.\n\n"
            pass
        elif expected_value in ['assertNull', 'assertNotNull']:
            instruction += f"- Either way, you **MUST** use `assertNull` or `assertNotNull` to check the result. You must give a **DIRECT PREDICTION** that is likely to pass execution based on your analysis and the advise.\n\n"
            pass
        else:
            instruction += f"- Either way, you **MUST** use `assertEquals` to verify the result, and **MUST NOT** use `<expected_value>` in the final response.\n\n"
        instruction += f'- The final assertion **MUST BE** surrounded by a code block in the format of markdown.'
        return instruction

    def differential_based_refine(self, **kwargs):
        guide = kwargs['guide']
        messages = kwargs['history'][self.__class__.__name__]
        expected_value = kwargs['expected_value']
        # actual_value = kwargs['actual_value']
        messages.append({
            'role': "user",
            'content': self._construct_instruction_for_differential_based_refine(guide, expected_value)
        })
        if expected_value in ['assertTrue', 'asertFalse', 'assertNull', 'assertNotNull']:
            prefix = 'Based on the advise, the final assertion should be:\n\n```java\nassert'
        else:
            prefix = 'Based on the advise, the final assertion should be:\n\n```java\nassertEquals('
        # response = self.model.get_response_with_prefix(messages, prefix=prefix)
        response = self.model.get_response(messages)
        self._history = messages
        self._record_history(role='assistant', content=response)
        return response

    def cross_validation_revise(self, **kwargs):
        base_messages = self.history[:-1]
        other_responses = kwargs['other_responses']
        prefix = kwargs['prefix']
        revised_responses = []
        for _, response in other_responses.items():
            argument = response['argument']
            new_response = self.model.get_response_with_prefix(base_messages,
                                                               prefix=argument + '\n\nBased on the above analysis, ' + prefix)
            revised_responses.append(new_response)
        return revised_responses

    def guided_refine(self, **kwargs):
        difference = kwargs['difference']
        previous_answers = kwargs['previous_answers']
        prefix = kwargs['prefix']
        messages = pickle.loads(pickle.dumps(self.history))
        instruction = "Now I have some different answers for the assertion to be added in the test case:\n"
        for ans in previous_answers:
            instruction += f'- {ans}\n\n'
        instruction += "Also, your superviser also made a comment about the differences between the answers:\n"
        instruction += f"\t{difference}\n\n"
        instruction += "Please provide a refined answer based on these information"
        messages.append({
            'role': 'user',
            'content': instruction
        })
        self._history = messages
        revised_response = self.model.get_response_with_prefix(messages, prefix)
        self._record_history('assistant', revised_response)
        return revised_response


class RAGGenerator(Generator):
    def __init__(self, model: LLM):
        self.system_prompt = "You are an expert in software testing, with 10 years of experience. You are very good at writing test cases."
        debate_system_prompt = ("You are an expert in software testing, with 10 years of experience. You are very good at writing test cases. "
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

    def _construct_instruction_all_in_one_with_code_feature(self, focal_method: str, test_prefix: str, retrieved_focal_method: str | None,
                                                            retrieved_test_case: str | None, focal_class_fields, focal_class_methods, test_class_fields,
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

    def _construct_instruction_all_in_one_for_assertBool(self, focal_method: str, test_prefix: str, retrieved_focal_method: str | None,
                                                         retrieved_test_case: str | None) -> str:
        instruction = "Your task is to help me add an assertion to help me verify the correctness of a method under testing. The method is \n```java\n" + \
            focal_method + "\n```\n Here is the test case for the above method: \n```java\n" + \
            test_prefix + "\n```\n"
        instruction += "Now I need your help on writing one assertion at the `<AssertionPlaceHolder>` line, following the code comment in the test case."
        if retrieved_focal_method and retrieved_test_case:
            instruction += 'Here is a similar focal method and its corresponding test case, I hope this could help you:\n```java\n' + \
                retrieved_focal_method + '\n' + retrieved_test_case + '\n```\n'
        instruction += 'Please read my code and write an assertion statement in the `<AssertionPlaceHolder>` line.\n' +\
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

    def _group_messages_v2_with_code_features(self, retrieved_focal_method: str, retrieved_test_case: str, focal_method: str,
                                              test_prefix: str, focal_class_fields, focal_class_methods, test_class_fields,
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

    def _group_messages_v2_for_assertBool(self, retrieved_focal_method: str, retrieved_test_case: str, focal_method: str,
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

class NaiveGenerator(Generator):
    def __init__(self, model: LLM):
        debate_system_prompt = ("You are an expert in software testing, with 10 years of experience. You are very good at writing test cases. "
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

    def _construct_instruction_for_assertBoolean(self, focal_method: str, test_prefix: str, expected_value_type: str | None) -> str:
        instruction = 'Your task is to complete the given test case. The method under testing is \n```java\n' + \
            focal_method + '\n```\n Here is part of the test case for the above method: \n```java\n' + \
            test_prefix + '\n```\n'
        instruction += 'Please read my code and write an assertion statement in the `<AssertionPlaceHolder>` line.\n' +\
            "You **MUST** use either `assertTrue()` or `assertFalse()` method to verify the result.\n" + \
            'Please write down the assertion and provide a short explaination. You should keep your answer within 200 words.'
        return instruction
        pass

    def _construct_instruction_with_code_features(self, focal_method: str, test_prefix: str, focal_class_fields: list,
                                                  focal_class_methods: list, test_class_fields: list, actual_value) -> str:
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

    def _construct_instruction_with_code_features_for_assertBoolean(self, focal_method: str, test_prefix: str, focal_class_fields: list,
                                                                    focal_class_methods: list, test_class_fields: list) -> str:
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
        instruction += 'Please read my code and write an assertion statement in the `<AssertionPlaceHolder>` line.\n' +\
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
                                           focal_class_methods: list, test_class_fields: list, actual_value: str) -> list:
        instruction = self._construct_instruction_with_code_features(focal_method, test_prefix, focal_class_fields,
                                                                     focal_class_methods, test_class_fields, actual_value)
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

    def _group_messages_for_assertBoolean(self, focal_method: str, test_prefix: str, expected_value_type: str | None) -> list:
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
                                                           focal_class_methods, test_class_fields, actual_value=kwargs['actual_value'])
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
                                                           focal_class_methods, test_class_fields, actual_value=kwargs['actual_value'])
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
        debate_system_prompt = ("You are an expert in software testing, with 10 years of experience. You are very good at writing test cases. "
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

    def final_round_messages(self, focal_method_name, focal_method, test_prefix, expected_value_type: str | None, actual_value: str):
        new_messages = pickle.loads(pickle.dumps(self._history))
        instruction = f'Based on your analysis, please accomplish the given test case by filling proper value in the `<expected_value>` part:\n```java\n{test_prefix}\n```\n'
        instruction += "\nPlease write down the completed assertion and provide a short explaination. You should keep your answer within 200 words. "
        new_messages.append({
            'role': 'user',
            'content': instruction
        })
        self.update_history(new_messages)
        return new_messages

    def final_round_messages_with_code_features(self, focal_method_name, focal_method, test_prefix, expected_value_type: str | None, focal_class_fields, focal_class_methods, test_class_fields):
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

    def final_round_messages_for_assertBoolean(self, focal_method_name, focal_method, test_prefix, expected_value_type: str | None):
        new_messages = pickle.loads(pickle.dumps(self._history))
        instruction = f'Based on your analysis, please accomplish the given test case by writing an assertion statement in the `<AssertionPlaceHolder>` line:\n```java\n{test_prefix}\n```\n'
        instruction += f"Please read my code and write an assertion statement in the `<AssertionPlaceHolder>` line." +\
            "Note that you **MUST** use either `assertTrue()` or `assertFalse()` method to verify the result." +\
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
            messages=self.final_round_messages_for_assertBoolean(focal_method_name, focal_method, test_prefix, expected_value_type))
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
        final_round_response = self.model.get_response(messages=self.final_round_messages_assertNullValues(focal_method_name, focal_method, test_prefix,
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


class Judge():
    def __init__(self, backend_model: LLM) -> None:
        self.model = backend_model
        self._history = []
        self.system_instruct = "You are a senior programmer and a leader of a software testing team."
        pass

    def analyze_difference(self, **kwargs):
        responses = [x.replace('\n', ' ') for x in kwargs['responses']]
        instruction = 'I asked some developers to help me generate an assertion for the test case. They have responsed with different opinions.\n'
        instruction += 'Here are their responses:\n'
        for response in responses:
            instruction += f'- {response}\n'
        instruction += 'Please read their arguments, and find out one crucial difference between them so that others can double-check their answers accordingly.\n'
        messages = [
            {'role': 'system', 'content': self.system_instruct},
            {'role': 'user', 'content': instruction}
        ]
        return self.model.get_response(messages)

    def verdict(self, **kwargs) -> str:
        response = ''
        messages = [
            # {'role':'system', 'content':self.system_instruct},
        ]
        expected_value = kwargs['expected_value']
        instruction = 'Your employees are arguing about writing proper assertions for a Java method, the method under test and the test case are:\n'
        instruction += f"```java\n//Below is the method under test\n{kwargs['focal_method']}\n\n//Here is the test case\n{kwargs['test_prefix']}\n```\n"
        if expected_value in ['assertTrue', 'assertFalse', 'assertNull', 'assertNotNull']:
            instruction += f'They are required to write a proper assertion using {expected_value} or the oppisite assertion method to test the subject mentioned in the comment in the test case.\n'
        else:
            instruction += 'They are required to accomplish the `assertEquals` statement in the test case by filling the `<expected_value>` part.'
        instruction += "Their answers are:\n\n"
        added = 0
        if kwargs['member_response']['Alice']:
            instruction += f"- **Alice**: {kwargs['member_response']['Alice']}\n\n"
            added += 1
        elif kwargs['member_response']['Bob']:
            instruction += f"- **Bob**: {kwargs['member_response']['Bob']}\n\n"
            added += 1
        elif kwargs['member_response']['Charlie']:
            instruction += f"- **Charlie**: {kwargs['member_response']['Charlie']}\n\n"
            added += 1
        if added == 0:
            instruction = instruction.replace("Their answers are:\n\n",
                                              'Unfortunately, they failed to give any possible assertions. Now I need you to help me write a proper assertion for the given test case.\n')
            instruction += "Let's think step by step:\n"
            instruction += "1. Identify the actual value of the test case, it could either be a value or expression for assertEquals or you need to decide which assert method (e.g., `assertTrue`, `assertFalse`, `assertNull` or `assertNotNull`) is reasonable.\n"
            instruction += "2. Read the method under test and the test case, find out what does the test case do.\n"
            instruction += "3. Based on your analysis, write down the final assertion.."
        else:

            instruction += "Please not that the confidence score only shows how confident they are about their own answer, not the actual correctness.\nLet's think step by step:\n"
            instruction += "1. Identify the actual value in the target assertion.\n"
            instruction += "2. Read the method under test and the test case, find out what does the test case do.\n"
            instruction += "3. Find out what did your teammates suggest as the expected value for the assertion.\n"
            instruction += "4. Judge which one of the proposed assertions is the most reasonable one.\n\n"
        instruction += "Please note that If the expected value has already been declaraed as a variable, it is mandatory to use it in the assertion.\nPlease directly give the assertion statement as the final judgement."
        # instruction += "You must **select one from your teammates'** as the final result, no modification is allowed and you must not use placeholders such as `<expected_value>`. Make sure the final answer of assertion is wraped in a markdown code block."

        messages.append({
            'role': 'user',
            'content': instruction
        })
        prefix = ''
        if expected_value in ['assertNull', 'assertNotNull', 'assertFalse', 'assertTrue']:
            if 'Null' in expected_value:
                prefix = f'Between `assertNull` and `assertNotNull`, I think the correct assertion is:\n```java\nassert'
                pass
            else:
                prefix = f'Between `assertTrue` and `assertFalse`, I think the correct assertion is:\n```java\nassert'
            pass
        else:
            prefix = 'By analyzing the given code, the type of the actual value of `assertEquals` and the opinions of the members, I think the the correct assertion is:\n```java\nassertEquals('
        response = self.model.get_response(messages)
        messages.append({
            'role': 'assistant',
            'content': response
        })
        messages.append({
            'role': 'user',
            'content': 'Thanks for your help. Now I need an assertion statement that can be directly added to the test case, please write down the assertion.\n'
        })
        # response = self.model.get_response(messages)
        response = self.model.get_response_with_prefix(messages=messages, prefix=prefix)
        messages.append({
            'role': 'assistant',
            'content': response
        })
        self._history = messages
        return response

    def verdict_with_confidence_score(self, **kwargs) -> str:
        response = ''
        messages = [
            # {'role':'system', 'content':self.system_instruct},
        ]
        expected_value = kwargs['expected_value']
        instruction = 'Your employees are arguing about writing proper assertions for a Java method, the method under test and the test case are:\n'
        instruction += f"```java\n//Below is the method under test\n{kwargs['focal_method']}\n\n//Here is the test case\n{kwargs['test_prefix']}\n```\n"
        if expected_value in ['assertTrue', 'assertFalse', 'assertNull', 'assertNotNull']:
            instruction += f'They are required to write a proper assertion using {expected_value} or the oppisite assertion method to test the subject mentioned in the comment in the test case.\n'
        else:
            instruction += 'They are required to accomplish the `assertEquals` statement in the test case by filling the `<expected_value>` part.'
        instruction += "Their answers are listed in the following, please noth that the confidence only shows how confident they are about their answer, not the actual correctness:\n\n"
        instruction += f"- **Alice**(Confidence: {kwargs['confidences']['Alice']}): {kwargs['member_response']['Alice']}\n\n"
        instruction += f"- **Bob**(Confidence: {kwargs['confidences']['Bob']}): {kwargs['member_response']['Bob']}\n\n"
        instruction += f"- **Charlie**(Confidence: {kwargs['confidences']['Charlie']}): {kwargs['member_response']['Charlie']}\n\n"
        instruction += "Please be careful for high confidence but incorrect assertions.\nLet's think step by step:\n"
        instruction += "1. Identify the actual value in the target assertion.\n"
        instruction += "2. Read the method under test and the test case, find out what does the test case do.\n"
        instruction += "3. Find out what did your teammates suggest as the expected value for the assertion.\n"
        instruction += "4. Judge which one of the proposed assertions is the most reasonable one.\n\n"
        instruction += "Please note that If the expected value has already been declaraed as a variable, it is mandatory to use it in the assertion.\n"
        # instruction += "You must **select one from your teammates'** as the final result, no modification is allowed and you must not use placeholders such as `<expected_value>`. Make sure the final answer of assertion is wraped in a markdown code block."

        messages.append({
            'role': 'user',
            'content': instruction
        })
        prefix = ''
        if expected_value in ['assertNull', 'assertNotNull', 'assertFalse', 'assertTrue']:
            if 'Null' in expected_value:
                prefix = f'Between `assertNull` and `assertNotNull`, I think the correct assertion is:\n```java\nassert'
                pass
            else:
                prefix = f'Between `assertTrue` and `assertFalse`, I think the correct assertion is:\n```java\nassert'
            pass
        else:
            prefix = 'By analyzing the given code, the type of the actual value of `assertEquals` and the opinions of the members, I think the the correct assertion is:\n```java\nassertEquals('
        response = self.model.get_response(messages)
        messages.append({
            'role': 'assistant',
            'content': response
        })
        messages.append({
            'role': 'user',
            'content': 'Thanks for your help. Now I need an assertion statement that can be directly added to the test case, please write down the assertion.\n'
        })
        # response = self.model.get_response(messages)
        response = self.model.get_response_with_prefix(messages=messages, prefix=prefix)
        messages.append({
            'role': 'assistant',
            'content': response
        })
        self._history = messages
        return response

    @property
    def history(self):
        return self._history

