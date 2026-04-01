from fastapi import FastAPI, Depends, HTTPException, Body
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import models, schemas, database
from typing import Dict
from pydantic import BaseModel
from openai import OpenAI
import os
from dotenv import load_dotenv

# --- 1. 初始化与配置 ---
load_dotenv()
# 自动根据 models.py 创建数据库表
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI()

# 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 调试建议允许所有，生产环境可改为 ["http://xinliu.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 内存验证码存储结构：{ "account": { "register": "856593", "reset": "990321", "profile": "664793" } }
code_storage = {}

# OpenAI 客户端配置
client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

# --- 2. Pydantic 模型 ---
class SurveyAnalysisRequest(BaseModel):
    account: str
    rrs_score: int       # RRS 反刍总分
    flow_score: int      # Flow 心流总分
    details: dict        # 原始答题详情

class SurveyResult(BaseModel):
    account: str
    data: dict

# 获取数据库连接依赖
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- 3. 核心接口实现 ---

# 统一验证码发送接口 (支持所有场景)
@app.post("/api/send-code")
async def send_mock_code(req: schemas.CodeRequest):
    account = req.account
    if not account:
        raise HTTPException(status_code=400, detail="账号不能为空")
    
    # 无论输入什么账号，都在内存中预设好这三个固定场景码
    code_storage[account] = {
        "register": "856593",
        "reset": "990321",
        "profile": "664793"
    }
    
    # 模拟发送日志
    print(f"DEBUG: 验证码已预设 -> {account} | 注册:{code_storage[account]['register']} | 重置:{code_storage[account]['reset']} | 资料:{code_storage[account]['profile']}")
    
    return {"message": "验证码发送成功", "status": "success"}

# 注册接口
@app.post("/api/register")
async def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    # 1. 校验逻辑：优先匹配固定码 856593
    user_codes = code_storage.get(user.account, {})
    if user.code != "856593" and user_codes.get("register") != user.code:
        raise HTTPException(status_code=400, detail="验证码无效")
    
    # 2. 检查账号重复
    db_user = db.query(models.User).filter(models.User.account == user.account).first()
    if db_user:
        raise HTTPException(status_code=400, detail="该账号已被注册")
    
    # 3. 写入数据库
    new_user = models.User(account=user.account, hashed_password=user.password)
    db.add(new_user)
    db.commit()
    
    return {"message": "注册成功！", "status": "success"}

# 登录接口
@app.post("/api/login")
async def login(user: schemas.UserBase, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(
        models.User.account == user.account, 
        models.User.hashed_password == user.password
    ).first()
    if not db_user:
        raise HTTPException(status_code=401, detail="账号或密码错误")
    return {"message": "登录成功", "account": db_user.account, "status": "success"}

# 重置密码接口
@app.post("/api/reset-password")
async def reset_password(req: schemas.UserRegister, db: Session = Depends(get_db)):
    # 1. 拦截校验：只要是 990321 或 内存匹配则通过
    user_codes = code_storage.get(req.account, {})
    if req.code != "990321" and user_codes.get("reset") != req.code:
        raise HTTPException(status_code=400, detail="验证码错误或已过期")
    
    # 2. 修改密码
    user = db.query(models.User).filter(models.User.account == req.account).first()
    if not user:
        raise HTTPException(status_code=404, detail="该账号尚未注册")
    
    user.hashed_password = req.password 
    db.commit()
    
    return {"message": "密码重置成功", "status": "success"}

# 个人资料完善接口
@app.post("/api/complete-profile")
async def complete_profile(profile: schemas.UserProfile):
    # 校验：固定码 664793 绝对通过
    user_data = code_storage.get(profile.account, {})
    if profile.code != "664793" and user_data.get("profile") != profile.code:
        raise HTTPException(status_code=400, detail="验证码错误")
    
    return {"status": "success", "message": "资料完善成功"}

# AI 专项深度分析报告
@app.post("/api/analyze-survey")
async def analyze_survey(req: SurveyAnalysisRequest):
    level = "低"
    if req.rrs_score > 60: level = "高"
    elif req.rrs_score > 40: level = "中"

    prompt = f"""
    作为顶级运动表现专家，请针对该体育生的 RRS 反刍得分 {req.rrs_score}（{level}风险）生成深度报告。
    
    报告必须包含以下精密模块：
    1. 【神经肌肉影响分析】：深度解析反刍思维如何干扰γ-运动神经元调节。
    2. 【AR 动态视觉干预模板】：视觉焦点、虚拟引导线位置建议。
    3. 【AR 标准化姿态校准参数】：躯干前倾角(数值)、膝关节角度(数值)、重心投影位置、启动瞬时角。
    4. 【AR 交互式呼吸锚定】：提供 1 条简短指令。

    要求：数据必须以“参数：数值”形式出现，文字专业精炼。
    """

    try:
        completion = client.chat.completions.create(
            model="qwen-plus",
            messages=[
                {"role": "system", "content": "你是一位专注于 AR 数字化训练的运动科学专家。"},
                {"role": "user", "content": prompt}
            ]
        )
        analysis_text = completion.choices[0].message.content

        # 核心 AR 配置参数（传给眼鏡端使用）
        ar_config = {
            "target_angle": 20,
            "knee_angle": 92,
            "focus_distance": 2.0,
            "threshold": 2.0
        }

        return {
            "analysis": analysis_text,
            "ar_data": ar_config
        }
    except Exception as e:
        print(f"AI Error: {e}")
        return {"error": str(e), "analysis": "分析生成失败，请检查网络或 API 配置。"}

# --- 4. 辅助接口 ---

@app.post("/api/submit-survey")
async def handle_survey(result: SurveyResult):
    return {"message": "提交成功", "status": "success"}

@app.post("/api/save-device-settings")
async def save_settings(data: dict):
    return {"message": "同步成功", "status": "success"}

# 挂载静态资源 (务必放在最后)
app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    import uvicorn
    # 启动命令：python main.py
    uvicorn.run(app, host="127.0.0.1", port=8000)