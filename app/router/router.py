import logging
import os
import traceback
import uuid
import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import List

import aiofiles
import httpx
import requests
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form
from pydantic import json
from sqlalchemy import select, insert, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from starlette.responses import FileResponse, StreamingResponse

from starlette.staticfiles import StaticFiles

from app.database import get_async_session

from app.shemas.schemas import AddRealEstate, FavoriteCreate, HomeBase, HomeBase2
from app.operations.crud import delete_item, update_item, delete_user, verify_token, get_coordinates, \
    get_options_by_home_id, fetch_news, parse_news, find_similar_announcements_by_price

from app.models.users import Home, User, FavoritesHome, Photo, Options, Visit

from app.models import users
from app.dependencies import get_current_user
from app.shemas.users import BaseUser, BaseUserWithRole, UpdateRoleRequest
from app.config import PHOTO_DIR
from app.operations import crud
from app.shemas import schemas

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

router.mount("/uploads", StaticFiles(directory="D:/flats/uploads"), name="uploads")


SPRING_BOOT_API_URL = "http://localhost:5050/api/record-visit"


# Убедитесь, что папка существует
os.makedirs(PHOTO_DIR, exist_ok=True)
# PHOTO_DIR.mkdir(parents=True, exist_ok=True)


logger = logging.getLogger(__name__)


@router.get("/announcements/{announcement_id}/similar_by_price", response_model=List[HomeBase2])
async def get_similar_announcements_by_price(
    announcement_id: int,
    db: AsyncSession = Depends(get_async_session),
    price_range_percentage: float = 10
):
    similar_announcements = await find_similar_announcements_by_price(
        announcement_id, db, price_range_percentage
    )

    # Преобразуем каждый результат в объект, который соответствует HomeBase
    return [HomeBase2(**announcement.__dict__) for announcement in similar_announcements]


@router.get("/itemsbyid")
async def get_items_by_user(user_id: int, db: AsyncSession = Depends(get_async_session)):
    # Выполнение запроса, чтобы получить все дома для данного пользователя
    result = await db.execute(
        select(Home)
        .filter(Home.user_id == user_id)  # Фильтрация по user_id
        .options(selectinload(Home.photos))  # Загружаем связанные фотографии
    )
    items = result.scalars().all()

    # Возвращаем список домов с добавленным путем к фотографии
    return [
        {
            "id": item.id,
            "name": item.name,
            "price": item.price,
            "description": item.description,
            "address": item.address,
            "photos": [photo.photo for photo in item.photos],  # Извлекаем имена фотографий
            "type_of_transaction": item.type_of_transaction,
            "type_of_housing": item.type_of_housing,
        }
        for item in items
    ]


# Эндпоинт для получения отзывов пользователя
@router.get("/reviews/{user_id}", response_model=list[schemas.Review])
async def get_reviews(user_id: int, db: AsyncSession = Depends(get_async_session)):
    reviews = await crud.get_reviews_by_user(db, user_id)
    if not reviews:
        raise HTTPException(status_code=404, detail="Отзывы не найдены")
    return reviews



# Эндпоинт для создания отзыва
@router.post("/reviews/", response_model=schemas.Review)
async def create_review(review: schemas.ReviewCreate, db: AsyncSession = Depends(get_async_session)):  # Зависимость без вызова
    return await crud.create_review(db=db, review=review)


@router.get("/users/{user_id}")
async def get_user(user_id: int, db: AsyncSession = Depends(get_async_session)):
    # Асинхронный запрос для получения пользователя
    result = await db.execute(select(User).filter(User.id == user_id))
    user = result.scalars().first()

    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    return user


@router.get("/news")
async def get_news():
    news = await parse_news()
    return {"news": news}


@router.post("/track-visit")
async def track_visit(user_id: str, db: AsyncSession = Depends(get_async_session)):
    # Сначала сохраняем информацию о визите в базу данных
    new_visit = Visit(user_id=user_id, visit_time=datetime.utcnow())

    db.add(new_visit)
    await db.commit()  # Асинхронный commit
    await db.refresh(new_visit)  # Асинхронный refresh для получения обновленного объекта

    # Отправляем запрос в Spring Boot API с использованием httpx
    payload = {"user_id": user_id}
    headers = {"Content-Type": "application/json"}

    async with httpx.AsyncClient() as client:
        response = await client.post(SPRING_BOOT_API_URL, json=payload, headers=headers)

    # Проверяем статус ответа от Spring Boot API
    if response.status_code == 200:
        return {"status": "success"}
    else:
        raise HTTPException(status_code=500, detail="Error while sending data to Spring Boot API")


@router.get("/count-users-today")
async def count_users_today():
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:5050/api/count-users-today")

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Error while fetching user count")

    return response.json()

@router.post("/add-real-estate/")
async def add_real_estate(
    name: str = Form(...),
    price: str = Form(...),
    type_of_transaction: str = Form(...),
    type_of_housing: str = Form(...),
    description: str = Form(...),
    address: str = Form(...),
    photos: list[UploadFile] = File(...),
    number_of_rooms: str = Form(...),  # Передаем количество комнат
    square: str = Form(...),  # Площадь
    year_of_construction: str = Form(...),  # Год постройки
    floor: str = Form(...),  # Этаж
    ceiling_height: str = Form(...),  # Высота потолков
    balcony: str = Form(...),  # Наличие балкона
    internet: str = Form(...),  # Наличие интернета
    elevator: str = Form(...),  # Наличие лифта
    db: AsyncSession = Depends(get_async_session),
    BaseUser: int = Depends(get_current_user),
):
    logger.info("Starting add_real_estate process")

    # Получение координат для адреса
    try:
        lat, lon = await get_coordinates(address)
        logger.info(f"Coordinates for address '{address}': lat={lat}, lon={lon}")
    except Exception as e:
        logger.error(f"Error geocoding address: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error geocoding address: {str(e)}")

    # Сохранение фотографий
    photo_names = []
    try:
        for photo in photos:
            unique_filename = f"{uuid.uuid4().hex}_{photo.filename}"
            photo_path = os.path.join(PHOTO_DIR, unique_filename)

            photo_names.append(unique_filename)
            logger.info(f"Saving photo: {unique_filename}")

            async with aiofiles.open(photo_path, 'wb') as out_file:
                while content := await photo.read(1024):
                    await out_file.write(content)
            logger.info(f"Photo saved: {unique_filename}")
    except Exception as e:
        logger.error(f"Error while saving photo: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error while saving photo: {str(e)}")

    # Создание нового дома в базе данных
    new_home = users.Home(
        name=name,
        price=price,
        type_of_transaction=type_of_transaction,
        type_of_housing=type_of_housing,
        description=description,
        address=address,
        latitude=lat,
        longitude=lon,
        user_id=BaseUser.id,
    )

    try:
        db.add(new_home)
        await db.commit()  # Коммитим, чтобы сохранить новый дом и присвоить ему ID
        await db.refresh(new_home)  # Обновляем объект new_home с ID из базы данных
        logger.info(f"Home created with ID: {new_home.id}")
    except Exception as e:
        await db.rollback()
        logger.error(f"Error during home creation: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error during home creation: {str(e)}")

    # Создание объекта Options с переданными параметрами
    try:
        new_options = users.Options(
            home_id=new_home.id,
            numbers_of_room=number_of_rooms,
            square=square,
            year_of_construction=year_of_construction,
            floor=floor,
            ceiling_height=ceiling_height,
            balcony=balcony,
            internet=internet,
            elevator=elevator
        )
        db.add(new_options)
        await db.commit()  # Коммитим изменения
        await db.refresh(new_home)  # Обновляем объект new_home с ID из базы данных
        logger.info(f"Options added to the database for home ID: {new_home.id}")
    except Exception as e:
        await db.rollback()
        logger.error(f"Error while adding options data to the database: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error while adding options data to the database: {str(e)}")

    # Создание записей для фотографий
    try:
        for photo_name in photo_names:
            new_photo = users.Photo(
                home_id=new_home.id,  # Связываем фото с домом
                photo=photo_name,  # Сохраняем имя файла
            )
            db.add(new_photo)

        await db.commit()  # Сохраняем фотографии в базе данных
        logger.info(f"Photos added to the database for home ID: {new_home.id}")
    except Exception as e:
        await db.rollback()
        logger.error(f"Error while adding photos to the database: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error while adding photos to the database: {str(e)}")

    return {"message": "Real estate added", "home_id": new_home.id}


@router.put("/edit-real-estate/{home_id}")
async def edit_real_estate(
    home_id: int,
    name: str = Form(...),
    price: str = Form(...),  # Цена как строка
    type_of_transaction: str = Form(...),
    type_of_housing: str = Form(...),
    description: str = Form(...),
    address: str = Form(...),
    photos: List[UploadFile] = File(None),  # Фотографии могут быть не переданы
    number_of_rooms: str = Form(...),  # Количество комнат как строка
    square: str = Form(...),  # Площадь как строка
    year_of_construction: str = Form(...),  # Год постройки как строка
    floor: str = Form(...),  # Этаж как строка
    ceiling_height: str = Form(...),  # Высота потолков как строка
    balcony: str = Form(...),  # Балкон как строка
    internet: str = Form(...),  # Интернет как строка
    elevator: str = Form(...),  # Лифт как строка
    db: AsyncSession = Depends(get_async_session),  # Подключение к базе данных
):
    logger.info(f"Начинаем процесс редактирования недвижимости для home_id {home_id}")

    # Получаем существующую недвижимость по ID
    existing_home = await db.execute(select(users.Home).filter(users.Home.id == home_id))
    home = existing_home.scalar_one_or_none()

    if not home:
        raise HTTPException(status_code=404, detail="Недвижимость не найдена")

    # Обновляем данные недвижимости как строки
    home.name = name
    home.price = price
    home.type_of_transaction = type_of_transaction
    home.type_of_housing = type_of_housing
    home.description = description
    home.address = address

    # Получаем координаты для адреса
    try:
        lat, lon = await get_coordinates(address)
        logger.info(f"Координаты для адреса '{address}': lat={lat}, lon={lon}")
        home.latitude = lat
        home.longitude = lon
    except Exception as e:
        logger.error(f"Ошибка при геокодировании адреса: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при геокодировании адреса: {str(e)}")

    # Обновляем параметры недвижимости как строки
    existing_options = await db.execute(select(users.Options).filter(users.Options.home_id == home_id))
    options = existing_options.scalar_one_or_none()

    if not options:
        raise HTTPException(status_code=404, detail="Параметры не найдены для этой недвижимости")

    # Обновляем параметры как строки, без конвертации
    options.numbers_of_room = number_of_rooms  # Количество комнат (строка)
    options.square = square  # Площадь (строка)
    options.year_of_construction = year_of_construction  # Год постройки (строка)
    options.floor = floor  # Этаж (строка)
    options.ceiling_height = ceiling_height  # Высота потолков (строка)
    options.balcony = balcony  # Балкон (строка)
    options.internet = internet  # Интернет (строка)
    options.elevator = elevator  # Лифт (строка)

    # Обрабатываем фотографии, если они переданы
    if photos:
        # Удаляем старые фотографии
        await db.execute(delete(users.Photo).filter(users.Photo.home_id == home_id))
        await db.commit()

        # Сохраняем новые фотографии
        photo_names = []
        try:
            for photo in photos:
                unique_filename = f"{uuid.uuid4().hex}_{photo.filename}"
                photo_path = os.path.join(PHOTO_DIR, unique_filename)

                photo_names.append(unique_filename)
                logger.info(f"Сохраняем фото: {unique_filename}")

                async with aiofiles.open(photo_path, 'wb') as out_file:
                    while content := await photo.read(1024):
                        await out_file.write(content)
                logger.info(f"Фото сохранено: {unique_filename}")
        except Exception as e:
            logger.error(f"Ошибка при сохранении фото: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Ошибка при сохранении фото: {str(e)}")

        # Добавляем новые фотографии в базу данных
        for photo_name in photo_names:
            new_photo = users.Photo(
                home_id=home.id,  # Связываем фото с домом
                photo=photo_name,  # Сохраняем имя файла
            )
            db.add(new_photo)
        logger.info(f"Фотографии обновлены для недвижимости с ID: {home.id}")

    # Сохраняем изменения в базе данных
    try:
        await db.commit()
        await db.refresh(home)
        logger.info(f"Недвижимость с ID {home.id} была обновлена")
    except Exception as e:
        await db.rollback()
        logger.error(f"Ошибка при обновлении недвижимости: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при обновлении недвижимости: {str(e)}")

    return {"message": "Недвижимость обновлена", "home_id": home.id}



@router.delete("/items/{item_id}")
async def delete_item_route(item_id: int, db: AsyncSession = Depends(get_async_session)):
    # Удаление всех фотографий, связанных с домом
    await db.execute(delete(Photo).where(Photo.home_id == item_id))
    await db.execute(delete(FavoritesHome).where(FavoritesHome.home_id == item_id))
    await db.execute(delete(Options).where(Options.home_id == item_id))
    # Теперь можно безопасно удалить сам дом
    await db.execute(delete(Home).where(Home.id == item_id))
    await db.commit()
    return {"detail": "Item deleted successfully"}


@router.put("/operations/items/{item_id}")
async def update_item_route(item_id: int, update_data: AddRealEstate, db: AsyncSession = Depends(get_async_session)):
    return await update_item(db, item_id, update_data)


@router.delete("/users/{user_id}", response_model=dict)
async def delete_user_endpoint(user_id: int, db: AsyncSession = Depends(get_async_session)):
    return await delete_user(db, user_id)


@router.get("/items/{id}")
async def get_item(id: int, db: AsyncSession = Depends(get_async_session)):
    # Получаем данные по ID из базы данных, включая связанные фотографии и опции
    result = await db.execute(
        select(Home)
        .options(selectinload(Home.photos), selectinload(Home.options))  # Загружаем фотографии и опции
        .filter(Home.id == id)
    )
    item = result.scalar_one_or_none()  # Получаем один результат или None

    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    options = await get_options_by_home_id(item.id, db)

    # Возвращаем данные в нужном формате, включая опции
    return {
        "id": item.id,
        "user_id": item.user_id,
        "name": item.name,
        "price": item.price,
        "description": item.description,
        "latitude": item.latitude,
        "longitude": item.longitude,
        "address": item.address,
        "type_of_transaction": item.type_of_transaction,
        "type_of_housing": item.type_of_housing,
        "photos": [photo.photo for photo in item.photos],  # Список фотографий
        "options": options
    }


@router.get("/items")
async def get_items(db: AsyncSession = Depends(get_async_session)):
    # Выполнение запроса, чтобы получить все дома вместе с их фотографиями
    result = await db.execute(
        select(Home)
        .options(selectinload(Home.photos))  # Используем selectinload для загрузки связанных фотографий
    )
    items = result.scalars().all()

    # Возвращаем список домов с добавленным путем к фотографии
    return [
        {
            "id": item.id,
            "name": item.name,
            "price": item.price,
            "description": item.description,
            "address": item.address,
            "photos": [photo.photo for photo in item.photos],  # Извлекаем имена фотографий
            "type_of_transaction": item.type_of_transaction,
            "type_of_housing": item.type_of_housing,

        }
        for item in items
    ]





@router.get("/users")
async def read_users(db: AsyncSession = Depends(get_async_session)):
    result = await db.execute(select(User))
    users = result.mappings().all()
    return users



# Функция для обновления роли пользователя
outer = APIRouter()


@router.put("/users/{user_id}/role")
async def update_role(user_id: int, request: UpdateRoleRequest, db: AsyncSession = Depends(get_async_session)):
    # Получаем пользователя из базы данных
    result = await db.execute(select(User).filter(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Обновляем роль пользователя
    user.role_id = request.role_id
    db.add(user)
    await db.commit()

    # Возвращаем обновленного пользователя
    return {"msg": "User role updated", "user": {"id": user.id, "username": user.username, "role_id": user.role_id}}


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

        # Формируем корректный URL для фото
        for real_estate in user_real_estate:
            real_estate.photo = f"http://127.0.0.1:8000/operations/get-photo/{Path(real_estate.photo).name}"

        return user_real_estate
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving data: {str(e)}")


@router.get("/get-photo/{home_id}")
async def get_photos_by_home(home_id: int, db: AsyncSession = Depends(get_async_session)):
    # Выполняем запрос к базе данных для получения всех фото для данного home_id
    result = await db.execute(select(Photo).filter(Photo.home_id == home_id))
    photos = result.scalars().all()

    if not photos:
        raise HTTPException(status_code=404, detail="No photos found for the given home ID")

    # Формируем пути к фотографиям
    photo_paths = [Path("uploads/photos") / photo.photo for photo in photos]

    # Проверяем существование файлов
    missing_files = [str(photo_path) for photo_path in photo_paths if not photo_path.exists()]
    if missing_files:
        raise HTTPException(status_code=404, detail=f"Files not found: {', '.join(missing_files)}")

    # Возвращаем список URL-адресов изображений
    # Здесь вместо путей мы формируем ссылку на изображение для клиента
    return [
        {"photo": str(photo_path.relative_to(Path("uploads/photos")))} for photo_path in photo_paths
    ]


@router.get("/get-photo/{home_id}/{photo_name}")
async def get_photo(home_id: int, photo_name: str, db: AsyncSession = Depends(get_async_session)):
    # Выполняем запрос к базе данных для получения всех фото для данного home_id
    result = await db.execute(select(Photo).filter(Photo.home_id == home_id))
    photos = result.scalars().all()

    if not photos:
        raise HTTPException(status_code=404, detail="No photos found for the given home ID")

    # Формируем путь к нужной фотографии
    photo = next((photo for photo in photos if photo.photo == photo_name), None)

    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    # Получаем путь к фотографии
    photo_path = Path("uploads/photos") / photo.photo

    # Проверяем существование файла
    if not photo_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    # Возвращаем сам файл фотографии
    return FileResponse(photo_path)

# @router.get("/get-photo/{home_id}")
# async def get_photo(home_id: int, db: AsyncSession = Depends(get_async_session)):
#     # Выполняем запрос к базе данных для получения всех фотографий для данного home_id
#     result = await db.execute(select(Photo).filter(Photo.home_id == home_id))
#     photos = result.scalars().all()  # Получаем все фотографии
#
#     if not photos:
#         raise HTTPException(status_code=404, detail="Photos not found")
#
#     # Формируем список путей к файлам фотографий
#     photo_paths = [Path(PHOTO_DIR) / photo.photo for photo in photos]
#
#     # Проверяем существование всех файлов фотографий
#     for photo_path in photo_paths:
#         if not photo_path.exists() or not photo_path.is_file():
#             raise HTTPException(status_code=404, detail=f"Photo file not found: {photo_path.name}")
#
#     # Создаем временный in-memory ZIP-архив
#     zip_buffer = BytesIO()
#     with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
#         for photo_path in photo_paths:
#             zip_file.write(photo_path, arcname=photo_path.name)
#
#     # Отправляем архив в ответе
#     zip_buffer.seek(0)
#     return StreamingResponse(zip_buffer, media_type="application/zip", headers={"Content-Disposition": "attachment; filename=photos.zip"})
#


# Пример маршрута, защищённого авторизацией
@router.get("/protected-route/")
def protected_route(current_user: dict = Depends(verify_token)):
    return {"message": "You have access to this route", "user": current_user}


@router.get("/user-info/")
def user_info(current_user: dict = Depends(verify_token)):
    return {"user_id": current_user["user_id"]}


@router.get('/me', response_model=BaseUserWithRole, tags=['auth'])
async def get_me(user: BaseUser = Depends(get_current_user)):
    return user.to_base_user_role()


@router.get("/ads/")
async def get_user_ads(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    # Асинхронный запрос объявлений пользователя с загрузкой связанных фотографий и опций
    result = await db.execute(
        select(Home)
        .where(Home.user_id == user.id)
        .options(selectinload(Home.photos), selectinload(Home.options))  # Загружаем options
    )
    user_ads = result.scalars().all()

    # Если объявления не найдены, выбрасываем исключение
    if not user_ads:
        raise HTTPException(status_code=404, detail="Объявления не найдены")

    # Преобразуем данные для возврата
    ads_data = [
        {
            "id": ad.id,
            "name": ad.name,
            "price": ad.price,
            "description": ad.description,
            "latitude": ad.latitude,
            "longitude": ad.longitude,
            "address": ad.address,
            "type_of_transaction": ad.type_of_transaction,
            "type_of_housing": ad.type_of_housing,
            "photos": [photo.photo for photo in ad.photos],  # Список фотографий
            "options": {
                "rooms": ad.options.numbers_of_room if ad.options and ad.options.numbers_of_room else '',
                "square": ad.options.square if ad.options and ad.options.square else '',
                "year_of_construction": ad.options.year_of_construction if ad.options and ad.options.year_of_construction else '',
                "floor": ad.options.floor if ad.options and ad.options.floor else '',
                "ceiling_height": ad.options.ceiling_height if ad.options and ad.options.ceiling_height else '',
                "balcony": ad.options.balcony if ad.options and ad.options.balcony else '',
                "internet": ad.options.internet if ad.options and ad.options.internet else '',
                "elevator": ad.options.elevator if ad.options and ad.options.elevator else '',



            }
        }
        for ad in user_ads
    ]
    return ads_data


@router.post("/favorites/")
async def add_to_favorites(
    favorite: FavoriteCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    # Проверяем, существует ли недвижимость
    query = select(Home).where(Home.id == favorite.home_id)
    result = await db.execute(query)
    home = result.scalar_one_or_none()
    if not home:
        raise HTTPException(status_code=404, detail="Home not found")

    # Проверяем, есть ли уже запись в избранном
    query = select(FavoritesHome).where(
        FavoritesHome.user_id == current_user.id,
        FavoritesHome.home_id == favorite.home_id
    )
    result = await db.execute(query)
    existing_favorite = result.scalar_one_or_none()
    if existing_favorite:
        raise HTTPException(status_code=400, detail="Already in favorites")

    # Добавляем запись в избранное
    new_favorite = FavoritesHome(user_id=current_user.id, home_id=favorite.home_id)
    db.add(new_favorite)
    await db.commit()
    return {"message": "Added to favorites"}


@router.delete("/favorites/{home_id}")
async def remove_from_favorites(
    home_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    # Проверяем, существует ли запись в избранном
    query = select(FavoritesHome).where(
        FavoritesHome.user_id == current_user.id,
        FavoritesHome.home_id == home_id
    )
    result = await db.execute(query)
    favorite = result.scalar_one_or_none()
    if not favorite:
        raise HTTPException(status_code=404, detail="Not in favorites")

    # Удаляем запись
    await db.delete(favorite)
    await db.commit()
    return {"message": "Removed from favorites"}


@router.get("/favorites/", response_model=List[HomeBase])
async def get_favorites(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    # Получаем все записи в избранном для текущего пользователя
    query = select(Home).join(FavoritesHome).where(FavoritesHome.user_id == current_user.id)
    result = await db.execute(query)
    homes = result.scalars().all()

    if not homes:
        raise HTTPException(status_code=404, detail="No favorites found")

    # Возвращаем список избранных домов как сериализованный список Pydantic моделей
    return homes