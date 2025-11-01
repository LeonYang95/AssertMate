from tkinter.ttk import Label

from loguru import logger


class Instance():
    def __init__(self, **kwargs):
        try:
            assert 'id' in kwargs and 'focal_method' in kwargs and 'test_case' in kwargs and 'test_prefix' in kwargs and 'assertion' in kwargs and 'focal_method_name' in kwargs
        except AssertionError:
            logger.error(
                'Missing one or more required arguments: id, focal_method, test_case, test_prefix, assertion, processed_assertion, focal_method_name.')
        self._idx = kwargs['id']
        self._focal_method = kwargs['focal_method']
        self._focal_method_name = kwargs['focal_method_name']
        self._test_case = kwargs['test_case']
        self._test_prefix = kwargs['test_prefix']
        self._assertion = kwargs['assertion']
        self._processed_assertion =''
        self._expected_value = ''
        self._actual_value = ''
        self._test_class_fields = kwargs['test_class_fields'] if 'test_class_fields' in kwargs else []
        self._focal_class_fields = kwargs['focal_class_fields'] if 'focal_class_fields' in kwargs else []
        self._focal_class_methods = kwargs['focal_class_methods'] if 'focal_class_methods' in kwargs else []
        self._invocations = kwargs['invocations'] if 'invocations' in kwargs else []
        pass

    def update(self, key, value):
        if key == 'expected_value':
            self._expected_value = value
        elif key == 'processed_assertion':
            self._processed_assertion =  value
        elif key == 'assertion':
            self._assertion = value
        elif key == 'test_prefix':
            self._test_prefix = value
        elif key =='actual_value':
            self._actual_value = value
        else:
            logger.error(f'Unknown key: {key}')

    @property
    def actual_value(self):
        return self._actual_value
    @property
    def test_prefix(self):
        return self._test_prefix
    @property
    def invocations(self):
        return self._invocations

    @property
    def focal_method_name(self):
        return self._focal_method_name

    @property
    def expected_value(self):
        return self._expected_value
    @property
    def processed_assertion(self):
        return self._processed_assertion

    @property
    def test_class_fields(self):
        return self._test_class_fields

    @property
    def focal_class_fields(self):
        return self._focal_class_fields

    @property
    def focal_class_methods(self):
        return self._focal_class_methods

    @property
    def id(self):
        return self._idx

    @property
    def test_case(self):
        return self._test_case

    @property
    def focal_method(self):
        return self._focal_method

    @property
    def assertion(self):
        return self._assertion
