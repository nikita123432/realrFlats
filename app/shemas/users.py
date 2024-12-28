import uuid
from typing import Optional

from fastapi_users import schemas

from pydantic import BaseModel, ConfigDict


class UserRead(schemas.BaseUser[int]):
    id: int
    email: str
    username: str
    role_id: int
    is_active: bool = True
    is_superuser: bool = False
    is_verified: bool = False

    model_config = ConfigDict(from_attributes=True)


class UpdateRoleRequest(BaseModel):
    role_id: int  # ID новой роли


class UserCreate(schemas.BaseUserCreate):
    username: str
    email: str
    password: str
    role_id: int
    is_active: Optional[bool] = True
    is_superuser: Optional[bool] = False
    is_verified: Optional[bool] = False


class UserUpdate(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None

    def create_update_dict_superuser(self):
        return self.model_dump(exclude_unset=True, exclude={"id"})


class BaseUser(BaseModel):
    id: int
    username: str
    email: str


class BaseUserWithRole(BaseModel):
    id: int
    username: str
    email: str
    role_id: int

