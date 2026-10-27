import uuid
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from database import get_db
from auth import pwd_context, create_access_token
from models import SignupRequest, LoginRequest
from repair_taxonomy import DORM_BUILDINGS
from phone_crypto import encrypt_phone, decrypt_phone

router = APIRouter()


@router.post("/api/register")
async def register(payload: SignupRequest):
    # 报修申请人统一注册为 user，可提交报修申请。
    role = 'user'

    name = payload.username.strip()
    phone = payload.phone.strip()
    student_id = payload.userId.strip()
    building = payload.dormBuilding.strip()
    if not name or not phone or not student_id or not building:
        raise HTTPException(status_code=400, detail="姓名、学号/工号、手机号和楼栋均为必填项")
    if building not in DORM_BUILDINGS:
        raise HTTPException(status_code=400, detail="楼栋选择无效")
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="密码长度不能少于6位")
    if payload.confirmPassword is not None and payload.password != payload.confirmPassword:
        raise HTTPException(status_code=400, detail="两次输入的密码不一致")

    conn = get_db()
    try:
        existing = conn.execute("SELECT id FROM users WHERE studentId = ?", (student_id,)).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="该学号/工号已注册")

        user_id = str(uuid.uuid4())
        now = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
        hashed_password = pwd_context.hash(payload.password or "")
        conn.execute(
            "INSERT INTO users (id, name, password, role, studentId, dormBuilding, phone, skills, createdAt) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, name, hashed_password, role, student_id, building, encrypt_phone(phone), "", now),
        )
        conn.commit()
    finally:
        conn.close()
    print(f"[/api/register] User account registered: {name} ({student_id})")
    return JSONResponse(
        status_code=201,
        content={"status": "success", "success": True, "message": "注册成功", "data": None},
    )


@router.post("/api/login")
async def login(payload: LoginRequest):
    identifier = payload.userId.strip()
    if not identifier:
        raise HTTPException(status_code=400, detail="请输入学号/工号")
    conn = get_db()
    try:
        user = conn.execute("SELECT * FROM users WHERE studentId = ? LIMIT 1", (identifier,)).fetchone()
    finally:
        conn.close()
    if not user:
        raise HTTPException(status_code=401, detail="学号/工号或密码错误")

    password_match = pwd_context.verify(payload.password, user["password"])
    if not password_match:
        raise HTTPException(status_code=401, detail="学号/工号或密码错误")

    username = user["studentId"] or identifier
    token = create_access_token(user["id"], user["name"], user["role"], username=username)
    print(f"[/api/login] Login successful: {user['name']} ({username})")
    return {
        "status": "success",
        "success": True,
        "token": token,
        "user": {
            "id": user["id"],
            "name": user["name"],
            "role": user["role"],
            "userId": user["studentId"],
            "dormBuilding": user["dormBuilding"] if "dormBuilding" in user.keys() else None,
            "dormRoom": user["dormRoom"],
            "phone": decrypt_phone(user["phone"]),
            "skills": user["skills"] if "skills" in user.keys() else None,
        },
    }
