from api import create_profile, schedule_event


def test_profile_defaults():
    profile = create_profile('ada')
    assert profile.handle == 'ada'
    assert profile.nickname is None
    assert profile.bio is None


def test_profile_with_nickname():
    assert create_profile('ada', 'countess').nickname == 'countess'


def test_event_without_location():
    assert schedule_event('sprint').location is None
