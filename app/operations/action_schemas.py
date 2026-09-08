from pydantic import BaseModel, EmailStr


class DigestRequest(BaseModel):
    recipient: EmailStr


class ActionResult(BaseModel):
    created: int = 0
    message: str
