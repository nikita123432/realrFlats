from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import HTTPException, Depends, Cookie
from starlette import status

from app.shemas.schemas import AddRealEstate
from app.models.users import User, Home
from app.config import SECRET_AUTH

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

ALGORITHM = "HS256"
SECRET_KEY = SECRET_AUTH


async def update_item(db: AsyncSession, item_id: int, updated_data: AddRealEstate):
    result = await db.execute(select(Home).where(Home.id == item_id))
    item = result.scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    updated_values = updated_data.dict(exclude_unset=True)

    await db.execute(update(Home).where(Home.id == item_id).values(**updated_values))
    await db.commit()

    return {"massage": "Item update successful"}


async def delete_item(db: AsyncSession, item_id: int):
    result = await db.execute(select(Home).where(Home.id == item_id))
    item = result.scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    await db.execute(delete(Home).where(Home.id == item_id))
    await db.commit()

    return {"message": "Item deleted successfully"}


# удаление юзиров
async def delete_user(db: AsyncSession, user_id: int):
    # Найти пользователя
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()

    if not user:
        raise ValueError(f"User with ID {user_id} not found")

    # Удалить пользователя
    await db.delete(user)
    await db.commit()
    return {"status": "success", "message": f"User with ID {user_id} deleted"}


def get_current_user_id(token: str = Depends(oauth2_scheme)) -> int:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        try:
            user_id = int(user_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user ID in token")

        return user_id
    except JWTError:
        # Если токен невалиден или произошла ошибка при декодировании
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def verify_token(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, "your-secret-key", algorithms=["HS256"])
        user_id = payload.get("sub")  # Обычно `sub` хранит идентификатор пользователя
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        return {"user_id": user_id}  # Возвращаем данные пользователя
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


