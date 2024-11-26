from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from fastapi_users import FastAPIUsers

from app.auth.base_config import auth_backend
from app.auth.manager import get_user_manager
from app.models.users import User


fastapi_users = FastAPIUsers[User, int](
    get_user_manager,
    [auth_backend],
)


def get_current_user(user: User = Depends(fastapi_users.current_user())):
    return user


def get_current_superuser(user: User = Depends(fastapi_users.current_user(active=True, superuser=True))):
    return user
