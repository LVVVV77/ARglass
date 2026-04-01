from sqlalchemy import Column, Integer, String
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    account = Column(String(50), unique=True, index=True) # 手机号或邮箱
    hashed_password = Column(String(100))