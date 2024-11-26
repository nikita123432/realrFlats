import os
from typing import List

import aiofiles
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form
from sqlalchemy import select, insert
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import FileResponse

from starlette.staticfiles import StaticFiles

from app.database import get_async_session

from app.shemas.schemas import AddRealEstate
from app.operations.crud import delete_item, update_item, delete_user, get_current_user_id, verify_token
from app.models.users import Home

from app.models import users
from app.dependencies import get_current_user
from app.shemas.users import BaseUser
from app.config import PHOTO_DIR

router = APIRouter(
    prefix="/operations",
    tags=["Operation"]
)


# функция добавления в бд
# @router.post("/add", response_model=AddRealEstate)
# async def add_real_estate(new_add: AddRealEstate, session: AsyncSession = Depends(get_async_session)):
#     stmt = insert(Home).values(**new_add.dict())
#     await session.execute(stmt)
#     await session.commit()
#     return new_add

router.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


# Убедитесь, что папка существует
os.makedirs(PHOTO_DIR, exist_ok=True)

@router.post("/add-real-estate/")
async def add_real_estate(
    name: str = Form(...),
    price: str = Form(...),
    type_of_transaction: str = Form(...),
    type_of_housing: str = Form(...),
    number_of_rooms: str = Form(...),
    description: str = Form(...),
    options: str = Form(...),
    address: str = Form(...),
    photo: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_session),
    BaseUser: int = Depends(get_current_user),
):
    # Генерация пути для фото
    photo_filename = f"{PHOTO_DIR}{photo.filename}"

    # Асинхронное сохранение фото
    try:
        async with aiofiles.open(photo_filename, 'wb') as out_file:
            while content := await photo.read(1024):  # Читаем файл частями
                await out_file.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error while saving photo: {str(e)}")

    # Создание записи в базе данных
    new_home = users.Home(
        name=name,
        price=price,
        type_of_transaction=type_of_transaction,
        type_of_housing=type_of_housing,
        number_of_rooms=number_of_rooms,
        description=description,
        options=options,
        address=address,
        photo=photo_filename,  # Сохраняем путь к фото
        user_id=BaseUser.id,
    )

    # Асинхронное добавление записи в базу данных
    try:
        db.add(new_home)
        await db.flush()  # Немедленно отправить изменения в базу
        await db.commit()
        await db.refresh(new_home)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error while adding data to the database: {str(e)}")

    return {"message": "Real estate added", "user_id": BaseUser.id}


@router.delete("/items/{item_id}")
async def delete_item_route(item_id: int, db: AsyncSession = Depends(get_async_session)):
    return await delete_item(db, item_id)


@router.put("/operations/items/{item_id}")
async def update_item_route(item_id: int, update_data: AddRealEstate, db: AsyncSession = Depends(get_async_session)):
    return await update_item(db, item_id, update_data)


@router.delete("users/{user_id}", response_model=dict)
async def delete_user_endpoint(user_id: int, db: AsyncSession = Depends(get_async_session)):
    return await delete_user(db, user_id)


@router.get("/items/{id}")
async def get_item(id: int, db: AsyncSession = Depends(get_async_session)):
    # Получаем данные по ID из базы данных
    result = await db.execute(select(Home).filter(Home.id == id))
    item = result.scalar_one_or_none()  # Получаем один результат или None
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

@router.get("/items")
async def get_items(db: AsyncSession = Depends(get_async_session)):
    result = await db.execute(select(Home))
    items = result.mappings().all()
    return items

@router.get("/get-real-estate/", response_model=List[AddRealEstate])
async def get_real_estate(
    db: AsyncSession = Depends(get_async_session),
    user=Depends(get_current_user),
):
    try:
        # Запрашиваем данные для текущего пользователя
        query = select(Home).where(Home.user_id == user.id)
        result = await db.execute(query)
        user_real_estate = result.scalars().all()

        if not user_real_estate:
            raise HTTPException(status_code=404, detail="No real estate found for the user")

        for real_estate in user_real_estate:
            real_estate.photo = f"http://127.0.0.1:8000/operations/get-photo/{real_estate.photo}"

        return user_real_estate
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving data: {str(e)}")


@router.get("/get-photo/{photo_filename}")
async def get_photo(photo_filename: str):
    photo_filename = os.path.basename(photo_filename)
    photo_path = os.path.join(PHOTO_DIR, photo_filename)
    if not os.path.exists(photo_path):
        raise HTTPException(status_code=404, detail="Photo not found")
    return FileResponse(photo_path)


# Пример маршрута, защищённого авторизацией
@router.get("/protected-route/")
def protected_route(current_user: dict = Depends(verify_token)):
    return {"message": "You have access to this route", "user": current_user}


@router.get("/user-info/")
def user_info(current_user: dict = Depends(verify_token)):
    return {"user_id": current_user["user_id"]}


@router.get('/me', response_model=BaseUser, tags=['auth'])
async def get_me(user: BaseUser = Depends(get_current_user)):
    return user.to_base_user()


@router.get("/ads/", response_model=List[AddRealEstate])
async def get_user_ads(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    # Асинхронный запрос объявлений пользователя
    result = await db.execute(
        select(Home).where(Home.user_id == user.id)
    )
    user_ads = result.scalars().all()

    if not user_ads:
        raise HTTPException(status_code=404, detail="Объявления не найдены")

    return user_ads  # SQLAlchemy объекты автоматически преобразуются в Pydantic

