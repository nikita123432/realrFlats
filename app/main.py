from fastapi import FastAPI, Depends
from fastapi_users import FastAPIUsers

from app.shemas.users import UserRead, UserCreate, BaseUser, UserUpdate

from fastapi.middleware.cors import CORSMiddleware
from app.router.router import router as router_operation, router
from app.auth.base_config import auth_backend
from app.auth.manager import get_user_manager
from app.models import users

app = FastAPI(
    title="Flats"
)


fastapi_users = FastAPIUsers[BaseUser, int](
    get_user_manager,
    [auth_backend],
)

app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/jwt",
    tags=["auth"],
)

app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    # prefix="/auth",
    tags=["auth"],
)



# app.include_router(
#     fastapi_users.get_users_router(UserRead, UserUpdate),
#     prefix="/users",
#     tags=["users"],
# )


app.include_router(router_operation)
# app.include_router(users.router)


origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
