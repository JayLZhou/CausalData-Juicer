from typing import Optional

from pydantic import BaseModel


class Profile(BaseModel):
    handle: str
    nickname: Optional[str]
    bio: Optional[str]


class Event(BaseModel):
    name: str
    location: Optional[str]
