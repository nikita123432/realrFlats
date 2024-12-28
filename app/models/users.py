from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import MetaData, Table, Column, Integer, String, TIMESTAMP, ForeignKey, JSON, Boolean, Float, DateTime
from sqlalchemy.orm import declarative_base, relationship

from app.shemas.users import BaseUser, BaseUserWithRole

Base = declarative_base()


class Role(Base):
    __tablename__ = "role"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    permissions = Column(JSON)


class User(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True)
    email = Column(String, nullable=False)
    username = Column(String, nullable=False)
    phone_number = Column(String)
    registered_at = Column(TIMESTAMP, default=datetime.utcnow)
    role_id = Column(Integer, ForeignKey("role.id"))
    hashed_password: str = Column(String(length=1024), nullable=False)
    is_active: bool = Column(Boolean, default=True, nullable=False)
    is_superuser: bool = Column(Boolean, default=False, nullable=False)
    is_verified: bool = Column(Boolean, default=False, nullable=False)

    reviews = relationship("ReviewModel", back_populates="user")

    favorites = relationship("Home", secondary="user_favorites", back_populates="favorited_by")

    def to_base_user(self):
        return BaseUser(id=self.id, username=self.username, email=self.email)

    def to_base_user_role(self):
        return BaseUserWithRole(id=self.id, username=self.username, email=self.email, role_id=self.role_id)


class Home(Base):
    __tablename__ = "home"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.id"))
    name = Column(String)
    price = Column(String)
    type_of_transaction = Column(String)
    type_of_housing = Column(String)
    description = Column(String)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    address = Column(String)
    # Связь с фотографиями
    photos = relationship("Photo", back_populates="home")
    options = relationship("Options", uselist=False, back_populates="home")


    # Связь с пользователями, которые добавили этот объект в избранное
    favorited_by = relationship("User", secondary="user_favorites", back_populates="favorites")


class Options(Base):
    __tablename__ = "options"

    id = Column(Integer, primary_key=True, autoincrement=True)
    home_id = Column(Integer, ForeignKey("home.id"))
    numbers_of_room = Column(String)
    square = Column(String)
    year_of_construction = Column(String)
    floor = Column(String)
    ceiling_height = Column(String)
    balcony = Column(String)
    internet = Column(String)
    elevator = Column(String)
    home = relationship("Home", back_populates="options")


class Photo(Base):
    __tablename__ = "photos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    home_id = Column(Integer, ForeignKey("home.id"))
    photo = Column(String)

    home = relationship("Home", back_populates="photos")


class FavoritesHome(Base):
    __tablename__ = "user_favorites"
    user_id = Column(Integer, ForeignKey("user.id"), primary_key=True)  # Исправление внешнего ключа
    home_id = Column(Integer, ForeignKey("home.id"), primary_key=True)  # Исправление внешнего ключа


class Visit(Base):
    __tablename__ = "visits"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)  # ID пользователя
    visit_time = Column(DateTime, default=datetime.utcnow)  # Время визита


    # Модель SQLAlchemy для отзыва
class ReviewModel(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), index=True)  # Связь с пользователем
    text = Column(String)

    user = relationship("User", back_populates="reviews")






