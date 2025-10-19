from pydantic import BaseModel, EmailStr, Field, ConfigDict
from datetime import date, datetime
from typing import Optional

from src.schemas.user import UserRead


class ContactSchema(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: str
    birthday: date
    extra_info: Optional[str] = None

class ContactCreate(ContactSchema):
    pass

class ContactUpdate(BaseModel):
    first_name: Optional[str]
    last_name: Optional[str]
    email: Optional[EmailStr]
    phone: Optional[str]
    birthday: Optional[date]
    extra_info: Optional[str]

class ContactResponse(ContactSchema):
    id: int
    # title: str
    # description: str
    # completed: bool
    created_at: datetime | None
    updated_at: datetime | None
    user: UserRead | None


    model_config = ConfigDict(from_attributes = True)
    # class Config:
    #     from_attributes  = True
