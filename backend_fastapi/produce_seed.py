"""Initialize production data with one administrator and the standard notices."""

import os
import sqlite3
import time
import uuid

from dotenv import load_dotenv
from passlib.context import CryptContext

load_dotenv()

from database import DB_PATH, migrate_phone_numbers, init_db
from phone_crypto import encrypt_phone
pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

ANNOUNCEMENTS = [
    "请遵守国家法律法规，禁止提交含有人身攻击、侮辱、诽谤、骚扰、侵害他人隐私、猥亵、淫秽色情、反动言论、虚假信息、有害内容或胁迫性文字的工单。",
    "报修工单用于受理公寓寝室内各类设施、设备的故障报修问题，处理范围包括：水电、门窗、锁具、家具、家电等问题。网络故障不属于报修工单处理范围。",
    "寝室号格式为“楼栋号-房间号”（例如：5-302）",
    "除卫生间堵塞等情况外，需拍摄现场照片，确保维修人员能直接识别问题。拍摄照片时请注意防止泄露个人隐私，避免出现广告、标语等无关内容，禁止使用修改、涂抹、添加滤镜文字或拼接图片。",
]


def now_str() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())


def seed() -> None:
    init_db()
    admin_name = os.getenv("SEED_ADMIN_NAME", "管理员").strip()
    admin_user_id = os.getenv("SEED_ADMIN_ID", "").strip()
    admin_password = os.getenv("SEED_ADMIN_PASSWORD", "")
    admin_phone = os.getenv("SEED_ADMIN_PHONE", "").strip()

    if not admin_name or not admin_user_id or not admin_password or not admin_phone:
        raise RuntimeError(
            "请在环境变量或 .env 中配置 SEED_ADMIN_NAME、SEED_ADMIN_ID、"
            "SEED_ADMIN_PASSWORD 和 SEED_ADMIN_PHONE。"
        )
    if len(admin_password) < 6:
        raise RuntimeError("SEED_ADMIN_PASSWORD 不能少于6位。")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        # Keep production seed runs consistent with the application's
        # encrypted-at-rest phone storage, including databases seeded earlier.
        migrate_phone_numbers(conn)

        existing_admin = conn.execute(
            "SELECT id FROM users WHERE studentId = ? AND role = 'admin' LIMIT 1",
            (admin_user_id,),
        ).fetchone()
        identifier_collision = conn.execute(
            "SELECT role FROM users WHERE studentId = ? LIMIT 1", (admin_user_id,)
        ).fetchone()
        if identifier_collision and identifier_collision["role"] != "admin":
            raise RuntimeError("SEED_ADMIN_ID 已被非管理员账号占用。")

        if existing_admin:
            admin_id = existing_admin["id"]
            print(f"管理员账号已存在，保留现有账号：{admin_user_id}")
        else:
            admin_id = str(uuid.uuid4())
            conn.execute(
                """INSERT INTO users
                   (id, name, password, role, studentId, phone, createdAt)
                   VALUES (?, ?, ?, 'admin', ?, ?, ?)""",
                (
                    admin_id,
                    admin_name,
                    pwd_context.hash(admin_password),
                    admin_user_id,
                    encrypt_phone(admin_phone),
                    now_str(),
                ),
            )
            print(f"已创建管理员账号：{admin_user_id}")

        added_announcements = 0
        for index, content in enumerate(ANNOUNCEMENTS, start=1):
            title = f"后勤公告{index}"
            exists = conn.execute(
                "SELECT 1 FROM announcements WHERE title = ? LIMIT 1", (title,)
            ).fetchone()
            if exists:
                continue
            conn.execute(
                """INSERT INTO announcements (id, title, content, authorId, createdAt)
                   VALUES (?, ?, ?, ?, ?)""",
                (str(uuid.uuid4()), title, content, admin_id, now_str()),
            )
            added_announcements += 1

        conn.commit()
        print(f"生产数据初始化完成：新增 {added_announcements} 条公告。")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
