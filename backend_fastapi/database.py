import os
import sqlite3
from phone_crypto import encrypt_phone, validate_phone_encryption_key

# ─── Paths ─────────────────────────────────────────────────────────────────────
DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "dorm.db"))
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")


# ─── Database Connection ──────────────────────────────────────────────────────
def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn


# ─── Schema Initialization ────────────────────────────────────────────────────
def init_db():
    """初始化数据库表结构"""
    validate_phone_encryption_key()
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            studentId TEXT,
            dormBuilding TEXT,
            dormRoom TEXT,
            phone TEXT,
            skills TEXT,
            createdAt TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS repairs (
            id TEXT PRIMARY KEY,
            studentId TEXT NOT NULL,
            dormBuilding TEXT NOT NULL,
            dormFloor INTEGER,
            dormRoom TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            imageUrl TEXT,
            status TEXT NOT NULL DEFAULT 'waiting',
            priority TEXT NOT NULL DEFAULT 'normal',
            assignedTo TEXT,
            adminNote TEXT,
            workNote TEXT,
            rating INTEGER,
            slaDueDate TEXT,
            slaBreached INTEGER DEFAULT 0,
            createdAt TEXT NOT NULL,
            updatedAt TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id TEXT PRIMARY KEY,
            requestId TEXT NOT NULL,
            studentId TEXT NOT NULL,
            rating INTEGER NOT NULL,
            createdAt TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id TEXT PRIMARY KEY,
            userId TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            type TEXT NOT NULL,
            relatedId TEXT,
            isRead INTEGER DEFAULT 0,
            createdAt TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS announcements (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            authorId TEXT NOT NULL,
            createdAt TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS parts (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            stock INTEGER NOT NULL,
            createdAt TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS repair_parts (
            id TEXT PRIMARY KEY,
            repairId TEXT NOT NULL,
            partId TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            createdAt TEXT NOT NULL
        )
    """)

    migration_add_columns(conn)
    _create_query_indexes(conn)

    # Encrypt legacy phone values atomically before the API starts.
    migrate_phone_numbers(conn)

    conn.commit()
    conn.close()


def migrate_phone_numbers(conn: sqlite3.Connection):
    """Encrypt any legacy plaintext phone values before the API starts."""
    rows = conn.execute(
        "SELECT id, phone FROM users WHERE phone IS NOT NULL AND phone != ''"
    ).fetchall()
    for row in rows:
        encrypted = encrypt_phone(row["phone"])
        if encrypted != row["phone"]:
            conn.execute("UPDATE users SET phone = ? WHERE id = ?", (encrypted, row["id"]))


def _create_query_indexes(conn: sqlite3.Connection):
    """Add indexes for the list, dashboard, notification, and SLA queries."""
    conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_users_student_id ON users(studentId);
        CREATE INDEX IF NOT EXISTS idx_users_role_created ON users(role, createdAt DESC);
        CREATE INDEX IF NOT EXISTS idx_repairs_student_created ON repairs(studentId, createdAt DESC);
        CREATE INDEX IF NOT EXISTS idx_repairs_assignee_status_due ON repairs(assignedTo, status, slaDueDate);
        CREATE INDEX IF NOT EXISTS idx_repairs_status_due ON repairs(status, slaDueDate);
        CREATE INDEX IF NOT EXISTS idx_notifications_user_created ON notifications(userId, createdAt DESC);
        CREATE INDEX IF NOT EXISTS idx_reviews_request ON reviews(requestId);
        CREATE INDEX IF NOT EXISTS idx_repair_parts_repair_created ON repair_parts(repairId, createdAt);
    """)


def migration_add_columns(conn: sqlite3.Connection):
    """为已有数据库添加评价及SLA相关字段（SQLite 不支持直接 ADD COLUMN IF NOT EXISTS）"""
    try:
        # Check users table
        user_columns = [row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()]
        if 'skills' not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN skills TEXT")
        if 'dormBuilding' not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN dormBuilding TEXT")
        # 检查 rating 字段是否存在
        columns = [row[1] for row in conn.execute("PRAGMA table_info(repairs)").fetchall()]
        if 'dormFloor' not in columns:
            conn.execute("ALTER TABLE repairs ADD COLUMN dormFloor INTEGER")
        if 'rating' not in columns:
            conn.execute("ALTER TABLE repairs ADD COLUMN rating INTEGER")
        if 'workNote' not in columns:
            conn.execute("ALTER TABLE repairs ADD COLUMN workNote TEXT")
        if 'slaDueDate' not in columns:
            conn.execute("ALTER TABLE repairs ADD COLUMN slaDueDate TEXT")
        if 'slaBreached' not in columns:
            conn.execute("ALTER TABLE repairs ADD COLUMN slaBreached INTEGER DEFAULT 0")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id TEXT PRIMARY KEY,
                userId TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                type TEXT NOT NULL,
                relatedId TEXT,
                isRead INTEGER DEFAULT 0,
                createdAt TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS announcements (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                authorId TEXT NOT NULL,
                createdAt TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS parts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                stock INTEGER NOT NULL,
                createdAt TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS repair_parts (
                id TEXT PRIMARY KEY,
                repairId TEXT NOT NULL,
                partId TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                createdAt TEXT NOT NULL
            )
        """)
    except Exception as e:
        print(f"[Migration] Error: {e}")


# ─── Status Constants ─────────────────────────────────────────────────────────
VALID_STATUSES = {'waiting', 'ready', 'in_progress', 'pending_evaluation', 'closed', 'rejected'}
STATUS_LABELS = {
    'waiting': '待接单',
    'ready': '已接单',
    'in_progress': '维修中',
    'pending_evaluation': '待评价',
    'closed': '已结案',
    'rejected': '已拒绝',
}
