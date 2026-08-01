from models import Event, Profile


def create_profile(handle, nickname=None):
    if nickname is None:
        return Profile(handle=handle)
    return Profile(handle=handle, nickname=nickname)


def schedule_event(name):
    return Event(name=name)
