from typing import List

from pydantic import BaseModel, Field, constr


class User(BaseModel):
    username: constr(regex=r'^[a-z][a-z0-9_]{2,15}$')
    tags: List[str] = Field(min_items=1, max_items=5)


def new_user(username, tags):
    return User(username=username, tags=list(tags))
