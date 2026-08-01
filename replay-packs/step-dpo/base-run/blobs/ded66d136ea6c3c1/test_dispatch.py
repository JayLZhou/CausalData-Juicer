from dispatch import current_args, usage_line


def test_explicit_args_passthrough():
    assert current_args(['a', 'b']) == ['a', 'b']


def test_os_args_shape():
    assert isinstance(current_args(), list)


def test_usage_line():
    assert usage_line('tool').startswith('usage: tool')
