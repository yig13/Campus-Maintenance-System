import os
import uuid
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query
from fastapi.responses import JSONResponse

from database import get_db, UPLOAD_DIR
from auth import verify_token, require_admin, pwd_context
from models import UpdateProfileRequest, ChangePasswordRequest, UpdateSkillsRequest, CreateAdminRequest, CreateRepairmanRequest
from repair_taxonomy import DORM_BUILDINGS, VALID_REPAIRMAN_SKILLS
from phone_crypto import encrypt_phone, decrypt_phone

router = APIRouter()


def _normalize_skills(skills: str) -> str:
    return ",".join(dict.fromkeys(
        skill.strip() for skill in skills.split(",")
        if skill.strip() in VALID_REPAIRMAN_SKILLS
    ))


@router.patch("/api/users/{user_id}/skills")
async def update_user_skills(user_id: str, payload: UpdateSkillsRequest, current_user: dict = Depends(require_admin)):
    conn = get_db()
    try:
        existing = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="用户不存在")

        conn.execute("UPDATE users SET skills = ? WHERE id = ?", (_normalize_skills(payload.skills), user_id))
        conn.commit()
    finally:
        conn.close()
    return {"success": True, "message": "技能更新成功"}


@router.get("/api/users")
def get_users(
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
    role: Optional[str] = None,
    current_user: dict = Depends(require_admin)
):
    conn = get_db()
    try:
        conditions = []
        params = []
        if role and role != "all":
            if role not in ("admin", "repairman", "user"):
                raise HTTPException(status_code=400, detail="用户身份筛选无效")
            conditions.append("role = ?")
            params.append(role)
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        total = conn.execute(f"SELECT COUNT(*) FROM users {where_clause}", params).fetchone()[0]
        query = f"SELECT id, name, role, studentId as userId, dormBuilding, dormRoom, phone, skills, createdAt FROM users {where_clause} ORDER BY createdAt DESC"
        query += " LIMIT ? OFFSET ?"
        query_params = [*params, pageSize, (page - 1) * pageSize]
        rows = conn.execute(query, query_params).fetchall()
    finally:
        conn.close()

    data = [dict(r) for r in rows]
    for user in data:
        user["phone"] = decrypt_phone(user.get("phone"))
        if user.get("role") == "repairman":
            user["skills"] = _normalize_skills(user.get("skills") or "")
    return {
        "success": True,
        "data": data,
        "total": total,
        "page": page,
        "pageSize": pageSize
    }


@router.get("/api/users/repairmen")
async def get_repairmen(current_user: dict = Depends(verify_token)):
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT u.id, u.name, u.studentId as userId, u.dormBuilding, u.role,
                   (SELECT COUNT(*) FROM repairs r
                    WHERE r.assignedTo = u.id AND r.status IN ('waiting', 'ready', 'in_progress')) as activeTasksCount
            FROM users u
            WHERE u.role = 'repairman'
        """).fetchall()
    finally:
        conn.close()
    return {"success": True, "data": [dict(r) for r in rows]}


@router.delete("/api/users/{user_id}")
async def delete_user(user_id: str, current_user: dict = Depends(require_admin)):
    if user_id == current_user.get("userId"):
        raise HTTPException(status_code=400, detail="不能删除当前登录的管理员账号")
    conn = get_db()
    try:
        user = conn.execute("SELECT id, role FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        if user["role"] == "repairman":
            active_tasks = conn.execute(
                "SELECT COUNT(*) FROM repairs WHERE assignedTo = ? AND status IN ('waiting', 'ready', 'in_progress')",
                (user_id,),
            ).fetchone()[0]
            if active_tasks:
                raise HTTPException(status_code=400, detail="该维修员仍有未完成工单，请先重新分配或释放工单")
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()
    return {"success": True, "data": None}


@router.get("/api/users/me")
async def get_current_user(current_user: dict = Depends(verify_token)):
    user_id = current_user.get("userId", "")
    conn = get_db()
    try:
        user = conn.execute(
            "SELECT id, name, role, studentId as userId, dormBuilding, dormRoom, phone, createdAt FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
    finally:
        conn.close()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user_data = dict(user)
    user_data["phone"] = decrypt_phone(user_data.get("phone"))
    return {"success": True, "data": user_data}


@router.post("/api/upload")
async def upload_image(file: UploadFile = File(...), current_user: dict = Depends(verify_token)):
    allowed_extensions = {".png", ".jpg", ".jpeg", ".gif"}
    _, ext = os.path.splitext(file.filename or "")
    ext = ext.lower()
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="只允许上传图片格式 (.png, .jpg, .jpeg, .gif)")

    max_size = 1024 * 1024 - 1
    content = bytearray()
    while chunk := await file.read(64 * 1024):
        content.extend(chunk)
        if len(content) > max_size:
            raise HTTPException(status_code=413, detail="图片必须小于1MB")

    image_signatures = {
        ".png": (b"\x89PNG\r\n\x1a\n",),
        ".jpg": (b"\xff\xd8\xff",),
        ".jpeg": (b"\xff\xd8\xff",),
        ".gif": (b"GIF87a", b"GIF89a"),
    }
    if not any(content.startswith(signature) for signature in image_signatures[ext]):
        raise HTTPException(status_code=400, detail="文件内容与图片格式不符")

    filename = f"{uuid.uuid4()}{ext.lower()}"
    file_path = os.path.join(UPLOAD_DIR, filename)

    try:
        with open(file_path, "wb") as f:
            f.write(content)
    except Exception as e:
        print(f"上传文件写入错误: {e}")
        raise HTTPException(status_code=500, detail="文件上传失败，请稍后重试")

    url = f"/uploads/{filename}"
    return {"success": True, "url": url}


@router.put("/api/users/profile")
async def update_profile(payload: UpdateProfileRequest, current_user: dict = Depends(verify_token)):
    user_id = current_user.get("userId", "")

    conn = get_db()
    try:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        updates = []
        values = []

        if payload.name is not None:
            updates.append("name = ?")
            values.append(payload.name)

        if payload.phone is not None:
            updates.append("phone = ?")
            values.append(encrypt_phone(payload.phone))

        if user["role"] == "user":
            if payload.userId is not None:
                student_id = payload.userId.strip()
                if not student_id:
                    raise HTTPException(status_code=400, detail="学号/工号不能为空")
                duplicate = conn.execute(
                    "SELECT id FROM users WHERE studentId = ? AND id != ?",
                    (student_id, user_id),
                ).fetchone()
                if duplicate:
                    raise HTTPException(status_code=400, detail="该学号/工号已被其他账号使用")
                updates.append("studentId = ?")
                values.append(student_id)
            if payload.dormBuilding is not None:
                if payload.dormBuilding not in DORM_BUILDINGS:
                    raise HTTPException(status_code=400, detail="楼栋选择无效")
                updates.append("dormBuilding = ?")
                values.append(payload.dormBuilding)
            if payload.dormRoom is not None:
                updates.append("dormRoom = ?")
                values.append(payload.dormRoom)
        elif user["role"] == "repairman" and payload.dormBuilding is not None:
            if payload.dormBuilding not in DORM_BUILDINGS:
                raise HTTPException(status_code=400, detail="楼栋选择无效")
            updates.append("dormBuilding = ?")
            values.append(payload.dormBuilding)

        if not updates:
            raise HTTPException(status_code=400, detail="未提供任何修改字段")

        values.append(user_id)
        conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", values)
        conn.commit()

        updated_user = conn.execute(
            "SELECT id, name, role, studentId as userId, dormBuilding, dormRoom, phone, createdAt FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
    finally:
        conn.close()

    print(f"[/api/users/profile] User profile updated: {user_id}")
    updated_data = dict(updated_user)
    updated_data["phone"] = decrypt_phone(updated_data.get("phone"))
    return {"success": True, "data": updated_data}


@router.post("/api/users/change-password")
async def change_password(payload: ChangePasswordRequest, current_user: dict = Depends(verify_token)):
    user_id = current_user.get("userId", "")

    if len(payload.newPassword) < 6:
        raise HTTPException(status_code=400, detail="新密码长度不能少于6位")

    if payload.newPassword != payload.confirmNewPassword:
        raise HTTPException(status_code=400, detail="两次输入的新密码不一致")

    conn = get_db()
    try:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        if not pwd_context.verify(payload.oldPassword, user["password"]):
            raise HTTPException(status_code=400, detail="当前密码输入错误")

        hashed_password = pwd_context.hash(payload.newPassword)
        conn.execute("UPDATE users SET password = ? WHERE id = ?", (hashed_password, user_id))
        conn.commit()
    finally:
        conn.close()

    print(f"[/api/users/change-password] Password changed for user: {user_id}")
    return {"success": True, "message": "密码修改成功"}


@router.post("/api/users/create-admin")
async def create_admin(payload: CreateAdminRequest, current_user: dict = Depends(require_admin)):
    name = payload.name.strip()
    user_id_value = payload.userId.strip()
    phone = payload.phone.strip()
    if not name or not user_id_value or not phone:
        raise HTTPException(status_code=400, detail="姓名、管理员账号、密码和手机号均为必填项")
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="密码长度不能少于6位")
    conn = get_db()
    try:
        existing = conn.execute("SELECT id FROM users WHERE studentId = ?", (user_id_value,)).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="该用户已被注册")
        user_id = str(uuid.uuid4())
        now = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
        hashed_password = pwd_context.hash(payload.password)
        conn.execute(
            "INSERT INTO users (id, name, password, role, studentId, phone, createdAt) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, name, hashed_password, "admin", user_id_value, encrypt_phone(phone), now),
        )
        conn.commit()
    finally:
        conn.close()
    print(f"[/api/users/create-admin] Admin created: {name} ({user_id_value})")
    return JSONResponse(
        status_code=201,
        content={"success": True, "message": "管理员创建成功", "data": {"id": user_id, "name": name, "userId": user_id_value, "role": "admin"}},
    )


@router.post("/api/users/create-repairman")
async def create_repairman(payload: CreateRepairmanRequest, current_user: dict = Depends(require_admin)):
    name = payload.name.strip()
    student_id = payload.userId.strip()
    phone = payload.phone.strip()
    building = (payload.dormBuilding or "").strip()
    if not name or not student_id or not phone:
        raise HTTPException(status_code=400, detail="姓名、学号/工号和手机号均为必填项")
    if building and building not in DORM_BUILDINGS:
        raise HTTPException(status_code=400, detail="楼栋选择无效")
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="密码长度不能少于6位")

    conn = get_db()
    try:
        existing = conn.execute("SELECT id FROM users WHERE studentId = ?", (student_id,)).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="该学号/工号已注册")

        user_id = str(uuid.uuid4())
        now = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
        hashed_password = pwd_context.hash(payload.password)
        conn.execute(
            "INSERT INTO users (id, name, password, role, studentId, dormBuilding, skills, phone, createdAt) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, name, hashed_password, "repairman", student_id, building or None, _normalize_skills(payload.skills), encrypt_phone(phone), now),
        )
        conn.commit()
    finally:
        conn.close()
    print(f"[/api/users/create-repairman] Repairman created: {name} ({student_id})")
    return JSONResponse(
        status_code=201,
        content={"success": True, "message": "维修员创建成功", "data": {"id": user_id, "name": name, "userId": student_id, "dormBuilding": building or None, "role": "repairman", "skills": _normalize_skills(payload.skills)}},
    )
