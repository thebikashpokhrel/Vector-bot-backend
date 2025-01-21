from pydantic import BaseModel
from typing import Optional


class User(BaseModel):
    client_id: str
    token: dict
