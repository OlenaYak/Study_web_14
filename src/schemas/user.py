from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional
from src.entity.models import Role



class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)


class UserRead(BaseModel):
    id: int
    username: str
    email: EmailStr
    avatar: Optional[str]
    role: Role

    model_config = ConfigDict(from_attributes = True)
    # class Config:
    #     from_attributes = True



class TokenSchema(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    refresh_token: str


class RequestEmail(BaseModel):
    email: EmailStr

