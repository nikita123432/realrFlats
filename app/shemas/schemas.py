from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict


class AddRealEstateCreate(BaseModel):
    name: str
    price: str
    description: str
    options: str
    address: str
    photo: str

    model_config = ConfigDict(from_attributes=True)


# Базовая схема для отзыва
class ReviewBase(BaseModel):
    user_id: int
    text: str


# Схема для создания отзыва
class ReviewCreate(ReviewBase):
    pass


# Схема для отображения отзыва
class Review(ReviewBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class AddRealEstate(BaseModel):
    id: int
    name: str
    price: str
    type_of_transaction: str
    type_of_housing: str
    number_of_rooms: str
    description: str
    options: str
    latitude: float | None = None  # Для широты
    longitude: float | None = None  # Для долготы
    address: str
    photo: str

    model_config = ConfigDict(from_attributes=True)


class Update(BaseModel):
    id: int
    name: str
    price: str
    type_of_transaction: str
    type_of_housing: str
    number_of_rooms: str
    description: str
    options: str
    address: str
    photo: str

    model_config = ConfigDict(from_attributes=True)


class FavoriteCreate(BaseModel):
    home_id: int

    model_config = ConfigDict(from_attributes=True)


class HomeBase(BaseModel):
    id: int
    name: str
    price: str
    address: str

    model_config = ConfigDict(from_attributes=True)


class HomeBase2(BaseModel):
    id: int
    user_id: int
    name: str
    price: str  # Здесь тип string, как в вашей SQLAlchemy модели
    type_of_transaction: str
    type_of_housing: str
    description: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: str
    photos: List[str] = []  # Можно использовать список ссылок на фотографии
    options: Optional[dict] = None  # Опции, если есть, могут быть словарем

    model_config = ConfigDict(from_attributes=True)


class Home(HomeBase2):
    pass


