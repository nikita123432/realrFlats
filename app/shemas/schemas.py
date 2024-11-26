from datetime import datetime
from typing import Optional

from pydantic import BaseModel




class AddRealEstateCreate(BaseModel):
    name: str
    price: str
    description: str
    options: str
    address: str
    photo: str


class AddRealEstate(BaseModel):
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

    class Config:
        orm_mode = True  # Включение режима ORM


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

    class Config:
        orm_mode = True  # Включение режима ORM





# class Сategories(BaseModel):
#     typeОfTransaction: str
#     typeOfHousing: str
#     numberOfRooms: str
#     price: str
#     address: str

