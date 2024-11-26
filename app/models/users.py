from datetime import datetime

from sqlalchemy import MetaData, Table, Column, Integer, String, TIMESTAMP, ForeignKey, JSON, Boolean
from sqlalchemy.orm import declarative_base

from app.shemas.users import BaseUser

Base = declarative_base()


class Role(Base):
    __tablename__ = "role"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    permissions = Column(JSON)


# Императивный
class User(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True)
    email = Column(String, nullable=False)
    username = Column(String, nullable=False)
    registered_at = Column(TIMESTAMP, default=datetime.utcnow)
    role_id = Column(Integer, ForeignKey("role.id"))
    hashed_password: str = Column(String(length=1024), nullable=False)
    is_active: bool = Column(Boolean, default=True, nullable=False)
    is_superuser: bool = Column(Boolean, default=False, nullable=False)
    is_verified: bool = Column(Boolean, default=False, nullable=False)

    def to_base_user(self):
        return BaseUser(id=self.id, username=self.username, email=self.email)


class Home(Base):
    __tablename__ = "home"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.id"))
    name = Column(String)
    price = Column(String)
    type_of_transaction = Column(String)  # Обратите внимание на корректное имя атрибута
    type_of_housing = Column(String)     # Аналогично
    number_of_rooms = Column(String)
    description = Column(String)
    options = Column(String)
    address = Column(String)
    photo = Column(String)
