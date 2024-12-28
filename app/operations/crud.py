from datetime import datetime, timedelta
from typing import List

import httpx
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from bs4 import BeautifulSoup
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from playwright.async_api import async_playwright
from sqlalchemy import select, delete, update, text, cast, Numeric
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import HTTPException, Depends, Cookie
from sqlalchemy.orm import joinedload
from sqlalchemy.sql.functions import user
from starlette import status

from decimal import Decimal

import app.database
from app.shemas.schemas import AddRealEstate
from app.models.users import User, Home, Options
from app.config import SECRET_AUTH
from app.shemas import schemas
from app.models import users

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

ALGORITHM = "HS256"
SECRET_KEY = SECRET_AUTH
YANDEX_API_KEY = "dad88f6c-dba8-4a6b-8a3f-c08810043cb8"



# Пример URL для парсинга новостей

url = "https://realt.by/news/"


async def find_similar_announcements_by_price(
        announcement_id: int, db: AsyncSession, price_range_percentage: float = 10
):
    # Получаем объявление по ID
    stmt = select(Home).where(Home.id == announcement_id)
    result = await db.execute(stmt)
    announcement = result.scalars().first()

    if not announcement:
        return []

    # Преобразуем цену из str в Decimal
    try:
        price = Decimal(announcement.price)  # Преобразуем строку в Decimal
    except Exception as e:
        # Если не удается преобразовать строку в число
        raise ValueError(f"Ошибка при преобразовании цены: {e}")

    # Определяем диапазон цен
    price_range_percentage_decimal = Decimal(price_range_percentage)  # Преобразуем в Decimal
    min_price = price * (1 - price_range_percentage_decimal / 100)
    max_price = price * (1 + price_range_percentage_decimal / 100)

    # Приводим поле price к типу NUMERIC
    stmt = select(Home).where(
        cast(Home.price, Numeric).between(min_price, max_price), Home.id != announcement.id
    )
    result = await db.execute(stmt)

    # Извлекаем все записи в виде списка
    similar_announcements = result.scalars().all()

    return similar_announcements




async def get_reviews_by_user(db: AsyncSession, user_id: int):
    result = await db.execute(select(users.ReviewModel).filter(users.ReviewModel.user_id == user_id))
    reviews = result.scalars().all()
    return reviews


# Создаем новый отзыв
async def create_review(db: AsyncSession, review: schemas.ReviewCreate):
    db_review = users.ReviewModel(user_id=review.user_id, text=review.text)
    db.add(db_review)
    await db.commit()  # Асинхронная коммитация
    await db.refresh(db_review)  # Асинхронное обновление
    return db_review


async def fetch_news():
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text


async def parse_news():
    html_content = await fetch_news()
    soup = BeautifulSoup(html_content, 'html.parser')
    all_news = soup.findAll('div', class_='bd-item')

    news_data = []

    for news in all_news:
        image_tag = news.find('img')
        image_url = image_tag['src'] if image_tag else None

        views_tag = news.find('span', class_='views')
        views = views_tag.get_text(strip=True) if views_tag else None

        title_tag = news.find('div', class_='title').find('a', class_='b12')
        title = title_tag.get_text(strip=True) if title_tag else None

        date_tag = news.find('span', class_='data')
        date = date_tag.get_text(strip=True) if date_tag else None

        content_tag = news.find('div', class_='bd-item-right-center-2')
        content = content_tag.get_text(strip=True) if content_tag else None

        news_data.append({
            'image_url': image_url,
            'views': views,
            'title': title,
            'date': date,
            'content': content,
        })

    return news_data


# scheduler = BackgroundScheduler()
#
# # Функция для очистки таблицы
# def clear_visits(db: AsyncSession):
#     now = datetime.now()
#     # Очистка записей, например, старше 30 дней
#     threshold_date = now - timedelta(days=30)
#     db.query(models.Visits).filter(models.Visits.created_at < threshold_date).delete()
#     db.commit()
#     print(f"Visits table cleared up to {threshold_date}")
#
# # Настройка задачи на очистку через 30 минут (можно настроить под свои нужды)
# scheduler.add_job(clear_visits,
#                   IntervalTrigger(minutes=30),  # Интервал в минутах
#                   args=[database.SessionLocal])  # Передаем сессию базы данных
#

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


#     Добавление объекта в избранное:
async def add_to_favorites(user_id: int, home_id: int, db: AsyncSession):
    result = await db.execute(select(User).options(joinedload(User.favorites)).filter(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise ValueError("User not found")

    result = await db.execute(select(Home).filter(Home.id == home_id))
    home = result.scalar_one_or_none()

    if not home:
        raise ValueError("Home not found")

    if home not in user.favorites:
        user.favorites.append(home)
        await db.commit()


# удаление из избранных
async def remove_from_favorites(user_id: int, home_id: int, db: AsyncSession):
    result = await db.execute(select(User).options(joinedload(User.favorites)).filter(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise ValueError("User not found")

    result = await db.execute(select(Home).filter(Home.id == home_id))
    home = result.scalar_one_or_none()

    if not home:
        raise ValueError("Home not found")

    if home in user.favorites:
        user.favorites.remove(home)
        await db.commit()


async def get_user_favorites(user_id: int, db: AsyncSession):
    result = await db.execute(select(User).options(joinedload(User.favorites)).filter(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise ValueError("User not found")

    return user.favorites


async def get_coordinates(address: str):
    base_url = "https://geocode-maps.yandex.ru/1.x/"
    params = {
        "apikey": YANDEX_API_KEY,
        "geocode": address,
        "format": "json"
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(base_url, params=params)
        if response.status_code == 200:
            geo_data = response.json()
            pos = (
                geo_data["response"]["GeoObjectCollection"]["featureMember"][0]
                ["GeoObject"]["Point"]["pos"]
            )
            lon, lat = map(float, pos.split())  # Координаты объекта
            return lat, lon
        else:
            raise Exception(f"Error fetching coordinates: {response.status_code}")


async def get_options_by_home_id(home_id: int, db: AsyncSession):
    # Выполняем запрос к базе данных для получения данных опций по home_id
    result = await db.execute(
        select(Options).filter(Options.home_id == home_id)
    )
    options = result.scalars().first()  # Получаем первый результат (если он есть)

    if options is None:
        return None  # Возвращаем None, если опции не найдены

    # Возвращаем словарь с опциями
    return {
        "numbers_of_room": options.numbers_of_room,
        "square": options.square,
        "year_of_construction": options.year_of_construction,
        "floor": options.floor,
        "ceiling_height": options.ceiling_height,
        "balcony": options.balcony,
        "internet": options.internet,
        "elevator": options.elevator,
    }



