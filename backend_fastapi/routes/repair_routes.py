import uuid
import time
import csv
import io
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse

from database import get_db, VALID_STATUSES, STATUS_LABELS
from auth import verify_token, require_admin
from models import CreateRepairRequest, UpdateRepairStatus, EvaluateRequest
from repair_taxonomy import DORM_BUILDINGS, DORM_APARTMENT_BUILDINGS, VALID_CATEGORIES
from phone_crypto import decrypt_phone

router = APIRouter()


def _mask_phone(phone: Optional[str]) -> str:
    """Hide the middle four digits while a repairman has not started the task."""
    if not phone:
        return ""
    digits = "".join(char for char in phone if char.isdigit())
    if len(digits) < 8:
        return "*" * len(digits)
    return f"{digits[:3]}****{digits[-4:]}"


@router.get("/api/repairs")
def get_repairs(
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
    status: Optional[str] = None,
    current_user: dict = Depends(verify_token)
):
    conn = get_db()
    role = current_user.get("role", "user")
    user_id = current_user.get("userId", "")

    try:
        conditions = []
        params = []

        if role == "repairman":
            conditions.append("(r.assignedTo = ? OR (r.assignedTo IS NULL AND r.status = 'waiting'))")
            params.append(user_id)
        elif role != "admin":
            conditions.append("r.studentId = ?")
            params.append(user_id)

        if status and status != "all":
            conditions.append("r.status = ?")
            params.append(status)

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        total_query = f"SELECT COUNT(*) FROM repairs r {where_clause}"
        total = conn.execute(total_query, params).fetchone()[0]

        status_counts = None
        if role == "repairman":
            visible_clause = "(assignedTo = ? OR (assignedTo IS NULL AND status = 'waiting'))"
            counts = conn.execute(
                f"SELECT status, COUNT(*) AS count FROM repairs WHERE {visible_clause} GROUP BY status",
                (user_id,),
            ).fetchall()
            count_map = {row["status"]: row["count"] for row in counts}
            status_counts = {
                "waiting": count_map.get("waiting", 0),
                "ready": count_map.get("ready", 0),
                "in_progress": count_map.get("in_progress", 0),
                "completed": count_map.get("pending_evaluation", 0) + count_map.get("closed", 0),
            }
            rating_row = conn.execute(
                "SELECT AVG(CASE WHEN status IN ('pending_evaluation', 'closed') THEN rating END) AS average, "
                "COUNT(CASE WHEN status IN ('pending_evaluation', 'closed') THEN rating END) AS count, "
                "COUNT(*) AS total FROM repairs WHERE assignedTo = ?",
                (user_id,),
            ).fetchone()
            status_counts["averageRating"] = rating_row["average"] or 0
            status_counts["ratingCount"] = rating_row["count"] or 0
            status_counts["totalAssigned"] = rating_row["total"] or 0

        # 维修员/管理员按紧急程度排序（待接单优先 + SLA截止时间升序），用户按创建时间倒序
        if role in ("repairman", "admin"):
            order_clause = """ORDER BY
                CASE r.status
                    WHEN 'waiting' THEN 1
                    WHEN 'ready' THEN 2
                    WHEN 'in_progress' THEN 3
                    WHEN 'pending_evaluation' THEN 4
                    WHEN 'closed' THEN 5
                    WHEN 'rejected' THEN 6
                    ELSE 7
                END,
                r.slaDueDate ASC"""
        else:
            order_clause = "ORDER BY r.createdAt DESC"

        data_query = f"""
            SELECT r.*,
                   r.studentId as userId,
                   u.name as userName,
                   u.phone as userPhone,
                   t.name as assignedToName
            FROM repairs r
            LEFT JOIN users u ON r.studentId = u.id
            LEFT JOIN users t ON r.assignedTo = t.id
            {where_clause}
            {order_clause}
        """

        if role == "repairman" and status == "completed":
            # “已完成”标签对应待评价和已结案两种最终状态。
            conditions[-1] = "r.status IN ('pending_evaluation', 'closed')"
            params.pop()  # completed 状态由 SQL 的两个最终状态固定展开，没有占位符。
            where_clause = "WHERE " + " AND ".join(conditions)
            data_query = f"""
                SELECT r.*,
                       r.studentId as userId,
                       u.name as userName,
                       u.phone as userPhone,
                       t.name as assignedToName
                FROM repairs r
                LEFT JOIN users u ON r.studentId = u.id
                LEFT JOIN users t ON r.assignedTo = t.id
                {where_clause}
                {order_clause}
            """
            total = status_counts["completed"]

        data_query += " LIMIT ? OFFSET ?"
        params.extend([pageSize, (page - 1) * pageSize])

        rows = conn.execute(data_query, params).fetchall()
    finally:
        conn.close()

    data = [dict(r) for r in rows]
    for repair in data:
        phone = decrypt_phone(repair.pop("userPhone", None))
        # 联系电话仅返回给该工单的维修人员。待接单时脱敏；
        # 维修人员开始处理后显示完整号码，便于联系预约上门。
        if role == "repairman":
            repair["userPhone"] = (
                _mask_phone(phone)
                if repair.get("status") == "waiting"
                else (phone or "")
            )
    response = {
        "success": True,
        "data": data,
        "total": total,
        "page": page,
        "pageSize": pageSize,
    }
    if status_counts is not None:
        response["statusCounts"] = status_counts
    return response


@router.post("/api/repairs")
async def create_repair(payload: CreateRepairRequest, current_user: dict = Depends(verify_token)):
    user_id = current_user.get("userId", "")
    role = current_user.get("role", "user")

    if role != "user":
        raise HTTPException(status_code=403, detail="只有普通用户可以提交报修申请")

    if payload.category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail="报修类型无效")

    image_urls = [url for url in (payload.imageUrl or "").split(",") if url.strip()]
    if len(image_urls) > 3:
        raise HTTPException(status_code=400, detail="故障照片最多上传3张")

    if payload.dormBuilding.strip() not in DORM_BUILDINGS:
        raise HTTPException(status_code=400, detail="楼栋无效")

    building = payload.dormBuilding.strip()
    floor = payload.dormFloor
    room = payload.dormRoom.strip()
    if not building or (building in DORM_APARTMENT_BUILDINGS and (floor is None or not room)) or not payload.description.strip():
        raise HTTPException(status_code=400, detail="请填写所有必填项")
    if len(payload.description) > 50:
        raise HTTPException(status_code=400, detail="故障详情最多可输入50字")

    repair_id = str(uuid.uuid4())
    now = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())

    # 用户提交的工单统一按普通优先级计算响应 SLA；优先级由管理员调整。
    priority = "normal"
    sla_due_date = (datetime.now(timezone.utc) + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    conn = get_db()
    try:
        assigned_to = None
        status = "waiting"
        admin_note = None

        conn.execute(
            """INSERT INTO repairs
               (id, studentId, dormBuilding, dormFloor, dormRoom, category, description, imageUrl, status, priority, assignedTo, adminNote, slaDueDate, slaBreached, createdAt, updatedAt)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (repair_id, user_id, building, floor, room, payload.category,
             payload.description, payload.imageUrl, status, priority, assigned_to, admin_note, sla_due_date, 0, now, now),
        )

        conn.commit()

        row = conn.execute("""
            SELECT r.*,
                   r.studentId as userId,
                   u.name as userName,
                   t.name as assignedToName
            FROM repairs r
            LEFT JOIN users u ON r.studentId = u.id
            LEFT JOIN users t ON r.assignedTo = t.id
            WHERE r.id = ?
        """, (repair_id,)).fetchone()
    finally:
        conn.close()

    print(f"[/api/repairs] Repair created: {repair_id} by {current_user.get('name')}")
    return {"success": True, "data": dict(row)}


@router.patch("/api/repairs/{repair_id}/status")
async def update_repair_status(repair_id: str, payload: UpdateRepairStatus, current_user: dict = Depends(verify_token)):
    role = current_user.get("role", "user")
    user_id = current_user.get("userId", "")
    now = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())

    conn = get_db()
    try:
        existing = conn.execute("SELECT * FROM repairs WHERE id = ?", (repair_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="报修记录不存在")

        if role == "user":
            raise HTTPException(status_code=403, detail="普通用户无法更新报修状态")

        if role == "repairman":
            claiming_unassigned = existing["assignedTo"] is None and existing["status"] == "waiting" and payload.status == "ready"
            if existing["assignedTo"] != user_id and not claiming_unassigned:
                raise HTTPException(status_code=403, detail="只能更新自己分配到的任务")
            if payload.status not in ("ready", "in_progress", "completed"):
                raise HTTPException(status_code=400, detail="维修人员只能接单、开始维修或完成维修")
            if payload.status == "ready" and existing["status"] != "waiting":
                raise HTTPException(status_code=400, detail="只有待接单工单可以接单")
            if payload.status == "in_progress" and existing["status"] != "ready":
                raise HTTPException(status_code=400, detail="只有已接单工单可以开始维修")
            if payload.status == "completed" and existing["status"] != "in_progress":
                raise HTTPException(status_code=400, detail="只有维修中的工单可以完成")
            if payload.status == "completed":
                if not payload.workNote or len(payload.workNote.strip()) < 5:
                    raise HTTPException(status_code=400, detail="完成维修时必须填写至少5个字的维修记录(workNote)")
                payload.status = "pending_evaluation"

                if payload.partsUsed:
                    for item in payload.partsUsed:
                        part = conn.execute("SELECT * FROM parts WHERE id = ?", (item.partId,)).fetchone()
                        if not part:
                            raise HTTPException(status_code=400, detail="所选配件不存在")

                        # 原子扣减：WHERE stock >= quantity 防止并发竞态
                        result = conn.execute(
                            "UPDATE parts SET stock = stock - ? WHERE id = ? AND stock >= ?",
                            (item.quantity, item.partId, item.quantity)
                        )
                        if result.rowcount == 0:
                            raise HTTPException(status_code=400, detail=f"配件 {part['name']} 库存不足（当前库存 {part['stock']}）")

                        part_usage_id = str(uuid.uuid4())
                        conn.execute(
                            "INSERT INTO repair_parts (id, repairId, partId, quantity, price, createdAt) VALUES (?, ?, ?, ?, ?, ?)",
                            (part_usage_id, repair_id, item.partId, item.quantity, part["price"], now)
                        )

        # Admin validations
        if role == "admin" and payload.status:
            valid_statuses = VALID_STATUSES
            if payload.status not in valid_statuses:
                raise HTTPException(status_code=400, detail="无效的状态")

        updates = []
        values = []

        if payload.status is not None:
            updates.append("status = ?")
            values.append(payload.status)

        if role == "repairman" and existing["assignedTo"] is None and payload.status == "ready":
            updates.append("assignedTo = ?")
            values.append(user_id)

        if payload.workNote is not None:
            updates.append("workNote = ?")
            values.append(payload.workNote)

        if role == "admin":
            if payload.assignedTo is not None:
                if payload.assignedTo:
                    assignee = conn.execute(
                        "SELECT id FROM users WHERE id = ? AND role = 'repairman'",
                        (payload.assignedTo,),
                    ).fetchone()
                    if not assignee:
                        raise HTTPException(status_code=400, detail="分配对象不是有效的维修员")
                updates.append("assignedTo = ?")
                values.append(payload.assignedTo if payload.assignedTo else None)
            if payload.adminNote is not None:
                updates.append("adminNote = ?")
                values.append(payload.adminNote)
            if payload.priority is not None:
                if payload.priority not in ("low", "normal", "high", "urgent"):
                    raise HTTPException(status_code=400, detail="优先级无效")
                if payload.priority != existing["priority"]:
                    updates.append("priority = ?")
                    values.append(payload.priority)
                    sla_hours = {"urgent": 2, "high": 6, "normal": 24, "low": 48}
                    hours = sla_hours.get(payload.priority, 24)
                    new_sla = (datetime.now(timezone.utc) + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
                    updates.append("slaDueDate = ?")
                    values.append(new_sla)

            # 管理员释放工单时按“重新提交”处理：重启响应 SLA 计时。
            if payload.status == "waiting" and payload.assignedTo == "":
                if payload.priority is None or payload.priority == existing["priority"]:
                    sla_hours = {"urgent": 2, "high": 6, "normal": 24, "low": 48}
                    hours = sla_hours.get(existing["priority"], 24)
                    new_sla = (datetime.now(timezone.utc) + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
                    updates.append("slaDueDate = ?")
                    values.append(new_sla)
                updates.append("slaBreached = 0")

        updates.append("updatedAt = ?")
        values.append(now)
        if role == "repairman" and existing["assignedTo"] is None and payload.status == "ready":
            cursor = conn.execute(
                f"UPDATE repairs SET {', '.join(updates)} WHERE id = ? AND assignedTo IS NULL AND status = 'waiting'",
                [*values, repair_id],
            )
            if cursor.rowcount == 0:
                raise HTTPException(status_code=409, detail="该工单已被其他维修员接单")
        else:
            conn.execute(f"UPDATE repairs SET {', '.join(updates)} WHERE id = ?", [*values, repair_id])
        row = conn.execute("""
            SELECT r.*,
                   r.studentId as userId,
                   u.name as userName,
                   t.name as assignedToName
            FROM repairs r
            LEFT JOIN users u ON r.studentId = u.id
            LEFT JOIN users t ON r.assignedTo = t.id
            WHERE r.id = ?
        """, (repair_id,)).fetchone()

        now_time = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
        if payload.status is not None and payload.status != existing["status"]:
            conn.execute(
                "INSERT INTO notifications (id, userId, title, message, type, relatedId, isRead, createdAt) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), existing["studentId"], "报修状态已更新", f"您的报修申请状态已更新为: {STATUS_LABELS.get(payload.status, payload.status)}", "repair_status", repair_id, 0, now_time)
            )

        assignment_changed = payload.assignedTo is not None and payload.assignedTo != existing["assignedTo"]
        if assignment_changed and payload.assignedTo:
            conn.execute(
                "INSERT INTO notifications (id, userId, title, message, type, relatedId, isRead, createdAt) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), payload.assignedTo, "新报修任务分配", "您有一个新的报修任务被分配", "repair_assigned", repair_id, 0, now_time)
            )
        if assignment_changed and existing["assignedTo"]:
            conn.execute(
                "INSERT INTO notifications (id, userId, title, message, type, relatedId, isRead, createdAt) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), existing["assignedTo"], "工单分配已变更", "管理员已调整该工单的维修员分配", "repair_assigned", repair_id, 0, now_time)
            )
        conn.commit()
    finally:
        conn.close()

    print(f"[/api/repairs/{repair_id}] Status updated by {current_user.get('name')}")
    return {"success": True, "data": dict(row)}


@router.post("/api/repairs/{repair_id}/evaluate")
async def evaluate_repair(repair_id: str, payload: EvaluateRequest, current_user: dict = Depends(verify_token)):
    """用户评价工单接口 - 将工单状态从 pending_evaluation 更新为 closed"""
    user_id = current_user.get("userId", "")
    role = current_user.get("role", "user")

    if role != "user":
        raise HTTPException(status_code=403, detail="只有普通用户可以评价")

    if payload.rating < 1 or payload.rating > 5:
        raise HTTPException(status_code=400, detail="评分必须在1-5之间")

    conn = get_db()
    try:
        existing = conn.execute("SELECT * FROM repairs WHERE id = ?", (repair_id,)).fetchone()

        if not existing:
            raise HTTPException(status_code=404, detail="报修记录不存在")

        if existing["studentId"] != user_id:
            raise HTTPException(status_code=403, detail="只能评价自己的报修")

        if existing["status"] != "pending_evaluation":
            raise HTTPException(status_code=400, detail="该工单当前不可评价")

        now = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())

        updated = conn.execute(
            """UPDATE repairs
               SET rating = ?, status = 'closed', updatedAt = ?
               WHERE id = ? AND studentId = ? AND status = 'pending_evaluation'""",
            (payload.rating, now, repair_id, user_id),
        )
        if updated.rowcount == 0:
            raise HTTPException(status_code=409, detail="工单已被评价或结案")

        review_id = str(uuid.uuid4())
        # 仅保存星级；评论字段保留在数据库中但不再写入用户评语。
        conn.execute(
            "INSERT INTO reviews (id, requestId, studentId, rating, createdAt) VALUES (?, ?, ?, ?, ?)",
            (review_id, repair_id, user_id, payload.rating, now),
        )
        conn.commit()

        row = conn.execute("""
            SELECT r.*,
                   r.studentId as userId,
                   u.name as userName,
                   t.name as assignedToName
            FROM repairs r
            LEFT JOIN users u ON r.studentId = u.id
            LEFT JOIN users t ON r.assignedTo = t.id
            WHERE r.id = ?
        """, (repair_id,)).fetchone()
    finally:
        conn.close()

    print(f"[/api/repairs/{repair_id}/evaluate] Evaluation submitted: {payload.rating} stars by {current_user.get('name')}")
    return {"success": True, "data": dict(row)}


@router.get("/api/repairs/export")
async def export_repairs(current_user: dict = Depends(require_admin)):
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT r.id, u.name as userName, r.dormBuilding, r.dormFloor, r.dormRoom,
                   r.category, r.status, r.priority, t.name as assignedToName,
                   r.createdAt, r.updatedAt
            FROM repairs r
            LEFT JOIN users u ON r.studentId = u.id
            LEFT JOIN users t ON r.assignedTo = t.id
            ORDER BY r.createdAt DESC
        """).fetchall()
    finally:
        conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Repair ID", "User Name", "Building", "Floor", "Room", "Category",
        "Status", "Priority", "Assigned Repairman", "Created At", "Updated At"
    ])

    for row in rows:
        writer.writerow([
            row["id"], row["userName"], row["dormBuilding"], row["dormFloor"], row["dormRoom"],
            row["category"], row["status"], row["priority"], row["assignedToName"],
            row["createdAt"], row["updatedAt"]
        ])

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=repairs_export.csv"}
    )
