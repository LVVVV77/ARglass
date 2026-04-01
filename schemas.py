from pydantic import BaseModel, EmailStr

class UserBase(BaseModel):
    account: str
    password: str

class UserCreate(UserBase):
    code: str  # 注册时需要验证码

class CodeRequest(BaseModel):
    account: str
    
class UserRegister(BaseModel):
    account: str
    password: str
    code: str = None

class UserProfile(BaseModel):
    account: str       # 手机号
    username: str      # 用户名
    password: str      # 密码
    email: str         # 邮箱
    id_card: str       # 身份证
    height: float      # 身高
    weight: float      # 体重
    gender: str        # 性别
    code: str          # 验证码