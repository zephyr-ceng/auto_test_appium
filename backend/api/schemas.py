from pydantic import BaseModel


class CookieUpdateRequest(BaseModel):
    cookie: str
