import pytest
from pydantic import ValidationError

from users import new_user


def test_valid_user():
    user = new_user('alice_01', ['admin'])
    assert user.username == 'alice_01'
    assert user.tags == ['admin']


def test_bad_username():
    with pytest.raises(ValidationError):
        new_user('9bad', ['x'])


def test_too_many_tags():
    with pytest.raises(ValidationError):
        new_user('alice_01', ['a', 'b', 'c', 'd', 'e', 'f'])


def test_empty_tags():
    with pytest.raises(ValidationError):
        new_user('alice_01', [])
