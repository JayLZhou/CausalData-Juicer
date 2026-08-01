from typing import Optional

from pydantic import BaseModel


class Profile(BaseModel):
    handle: str
    nickname: Optional[str] = None
    bio: Optional[str] = None


class Event(BaseModel):
    name: str
    location: Optional[str] = None
