import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from database import get_db
from repair_taxonomy import CATEGORY_TO_SKILL


AUTO_DISPATCH_WAIT_HOURS = {"urgent": 1, "high": 2, "normal": 4, "low": 8}


def dispatch_unaccepted_repairs(conn, now_utc: datetime, now_str: str):
    """派发等待超过优先级时限、仍未分配维修员的工单。"""
    waiting_repairs = conn.execute("""
        SELECT id, studentId, dormBuilding, dormRoom, category, priority, adminNote, updatedAt
        FROM repairs
        WHERE status = 'waiting' AND assignedTo IS NULL
    """).fetchall()
    if not waiting_repairs:
        return

    repairmen = conn.execute(
        "SELECT id, name, skills FROM users WHERE role = 'repairman'"
    ).fetchall()
    for repair in waiting_repairs:
        try:
            waiting_since = datetime.fromisoformat(repair["updatedAt"].replace("Z", "+00:00"))
            if waiting_since.tzinfo is None:
                waiting_since = waiting_since.replace(tzinfo=timezone.utc)
        except (ValueError, AttributeError):
            print(f"[Auto Dispatch] Invalid createdAt for repair {repair['id']}")
            continue

        wait_hours = AUTO_DISPATCH_WAIT_HOURS.get(repair["priority"], 4)
        if (now_utc - waiting_since).total_seconds() < wait_hours * 3600:
            continue

        skill_group = CATEGORY_TO_SKILL.get(repair["category"])
        candidates = []
        for repairman in repairmen:
            skills = [skill.strip() for skill in (repairman["skills"] or "").split(",")]
            if not skill_group or skill_group not in skills:
                continue
            active_count = conn.execute(
                "SELECT COUNT(*) FROM repairs WHERE assignedTo = ? AND status IN ('waiting', 'ready', 'in_progress')",
                (repairman["id"],),
            ).fetchone()[0]
            if active_count < 5:
                candidates.append((active_count, repairman["name"], repairman["id"]))

        if not candidates:
            # 保持未分配状态，下轮轮询继续尝试，避免无技能或满载时误派。
            continue

        active_count, name, repairman_id = min(candidates, key=lambda item: (item[0], item[1]))
        note = f"[系统派单] 超过{wait_hours}小时无人接单，技能匹配+负载均衡（当前 {active_count} 单），自动分配给：{name}"
        if repair["adminNote"]:
            note = f"{note}\n{repair['adminNote']}"

        # 条件更新可防止管理员同时手动分配时覆盖其操作。
        updated = conn.execute(
            "UPDATE repairs SET assignedTo = ?, adminNote = ?, updatedAt = ? WHERE id = ? AND status = 'waiting' AND assignedTo IS NULL",
            (repairman_id, note, now_str, repair["id"]),
        )
        if updated.rowcount == 0:
            continue

        conn.execute(
            "INSERT INTO notifications (id, userId, title, message, type, relatedId, isRead, createdAt) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), repairman_id, "新报修任务分配", f"工单（{repair['dormBuilding']} {repair['dormRoom']}）已由系统自动派单，请及时处理。", "repair_assigned", repair["id"], 0, now_str),
        )
        conn.execute(
            "INSERT INTO notifications (id, userId, title, message, type, relatedId, isRead, createdAt) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), repair["studentId"], "报修工单已自动派单", f"您的工单（{repair['dormBuilding']} {repair['dormRoom']}）已分配给维修员：{name}。", "repair_assigned", repair["id"], 0, now_str),
        )
        print(f"[Auto Dispatch] Repair {repair['id']} assigned to {name} after {wait_hours} hours.")


def close_unrated_repairs(conn, now_utc: datetime, now_str: str):
    """24小时未评价的工单自动记5星并结案。"""
    pending = conn.execute("""
        SELECT id, studentId, assignedTo, dormBuilding, dormRoom, updatedAt
        FROM repairs
        WHERE status = 'pending_evaluation' AND rating IS NULL
          AND NOT EXISTS (SELECT 1 FROM reviews WHERE reviews.requestId = repairs.id)
    """).fetchall()
    cutoff = now_utc - timedelta(hours=24)

    for repair in pending:
        try:
            pending_since = datetime.fromisoformat(repair["updatedAt"].replace("Z", "+00:00"))
            if pending_since.tzinfo is None:
                pending_since = pending_since.replace(tzinfo=timezone.utc)
        except (ValueError, AttributeError):
            print(f"[Auto Evaluation] Invalid updatedAt for repair {repair['id']}")
            continue

        if pending_since > cutoff:
            continue

        # 条件更新防止覆盖刚刚提交的用户评价或管理员状态修改。
        updated = conn.execute("""
            UPDATE repairs
            SET rating = 5, status = 'closed', updatedAt = ?
            WHERE id = ? AND status = 'pending_evaluation'
              AND rating IS NULL AND updatedAt = ?
        """, (now_str, repair["id"], repair["updatedAt"]))
        if updated.rowcount == 0:
            continue

        conn.execute(
            "INSERT INTO reviews (id, requestId, studentId, rating, createdAt) VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), repair["id"], repair["studentId"], 5, now_str),
        )
        conn.execute(
            "INSERT INTO notifications (id, userId, title, message, type, relatedId, isRead, createdAt) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), repair["studentId"], "工单已自动结案", f"工单（{repair['dormBuilding']} {repair['dormRoom']}）超过24小时未评价，系统已默认5星好评并结案。", "repair_status", repair["id"], 0, now_str),
        )
        print(f"[Auto Evaluation] Repair {repair['id']} automatically rated 5 stars and closed.")


async def check_sla_compliance():
    """检测工单 SLA 的状态，处理即将超期预警与已超期强力干预"""
    conn = get_db()
    try:
        now_utc = datetime.now(timezone.utc)
        now_str = now_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z")

        dispatch_unaccepted_repairs(conn, now_utc, now_str)
        close_unrated_repairs(conn, now_utc, now_str)
        conn.commit()

        # 查找所有未完成的工单 (waiting, ready, in_progress)
        active_repairs = conn.execute("""
            SELECT id, studentId, dormBuilding, dormRoom, category, status, priority, assignedTo, adminNote, createdAt, slaDueDate, slaBreached
            FROM repairs
            WHERE status IN ('waiting', 'ready', 'in_progress')
        """).fetchall()

        for r in active_repairs:
            repair_id = r["id"]
            created_str = r["createdAt"]
            due_str = r["slaDueDate"]
            priority = r["priority"]
            assigned_to = r["assignedTo"]
            dorm_building = r["dormBuilding"]
            dorm_room = r["dormRoom"]
            admin_note = r["adminNote"]

            try:
                created_dt = datetime.fromisoformat(created_str.replace('Z', '+00:00'))
                due_dt = datetime.fromisoformat(due_str.replace('Z', '+00:00'))
            except Exception as e:
                print(f"[SLA Check] Time parse error for repair {repair_id}: {e}")
                continue

            total_duration_sec = (due_dt - created_dt).total_seconds()
            remaining_sec = (due_dt - now_utc).total_seconds()

            # 计算是否到达 80% 的阀值（即剩余时间少于 20%）
            warning_threshold = total_duration_sec * 0.20

            # (A) 超期检测
            if remaining_sec <= 0 and r["slaBreached"] == 0:
                conn.execute("UPDATE repairs SET slaBreached = 1, updatedAt = ? WHERE id = ?", (now_str, repair_id))

                # 1. 给报修用户发送加急通知
                conn.execute(
                    "INSERT INTO notifications (id, userId, title, message, type, relatedId, isRead, createdAt) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), r["studentId"], "⏳ 报修服务加急提醒", f"您的工单（{dorm_building} {dorm_room}）已超出响应时效，系统已提醒管理员加急处理。", "sla_breached", repair_id, 0, now_str)
                )

                # 2. 如果分配了维修员，给维修员发送超期警告
                if assigned_to:
                    conn.execute(
                        "INSERT INTO notifications (id, userId, title, message, type, relatedId, isRead, createdAt) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (str(uuid.uuid4()), assigned_to, "🚨 工单超期警告", f"工单（{dorm_building} {dorm_room}）已超期未解决，请立即处理并联系报修用户说明情况！", "sla_breached", repair_id, 0, now_str)
                    )

                # 3. 给所有管理员发送预警通知
                admins = conn.execute("SELECT id FROM users WHERE role = 'admin'").fetchall()
                for admin in admins:
                    conn.execute(
                        "INSERT INTO notifications (id, userId, title, message, type, relatedId, isRead, createdAt) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (str(uuid.uuid4()), admin["id"], "⚠️ 工单超期督办", f"工单（{dorm_building} {dorm_room}，优先级: {priority}）已超期，需要您的介入督办。", "sla_breached", repair_id, 0, now_str)
                    )

                # 自动在工单管理员备注中记录
                new_admin_note = "[⚠️ SLA超期警报] 该工单已超时未解决，自动提醒管理员干预。"
                if admin_note:
                    updated_note = f"{new_admin_note}\n{admin_note}"
                else:
                    updated_note = new_admin_note
                conn.execute("UPDATE repairs SET adminNote = ? WHERE id = ?", (updated_note, repair_id))
                conn.commit()
                print(f"[SLA Compliance] Repair {repair_id} breached SLA. Sent notifications.")

            # (B) 即将超期警告 (剩余时间少于 20% 且大于 0 且之前未发过该工单的超期预警通知)
            elif 0 < remaining_sec <= warning_threshold:
                already_warned = conn.execute(
                    "SELECT COUNT(*) FROM notifications WHERE relatedId = ? AND type = 'sla_warning'",
                    (repair_id,)
                ).fetchone()[0]

                if already_warned == 0:
                    if assigned_to:
                        conn.execute(
                            "INSERT INTO notifications (id, userId, title, message, type, relatedId, isRead, createdAt) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                            (str(uuid.uuid4()), assigned_to, "⏳ 任务即将超期", f"您的任务（{dorm_building} {dorm_room}）即将超时（剩余 {int(remaining_sec / 60)} 分钟），请尽快处理！", "sla_warning", repair_id, 0, now_str)
                        )
                    else:
                        admins = conn.execute("SELECT id FROM users WHERE role = 'admin'").fetchall()
                        for admin in admins:
                            conn.execute(
                                "INSERT INTO notifications (id, userId, title, message, type, relatedId, isRead, createdAt) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                (str(uuid.uuid4()), admin["id"], "⏳ 待办任务即将超时", f"工单（{dorm_building} {dorm_room}）即将超时（剩余 {int(remaining_sec / 60)} 分钟）且尚未分配，请尽快处理！", "sla_warning", repair_id, 0, now_str)
                            )
                    conn.commit()
                    print(f"[SLA Compliance] Repair {repair_id} warning threshold reached. Sent alert notifications.")
    except Exception as e:
        print(f"[SLA Compliance] Error in check_sla_compliance: {e}")
    finally:
        conn.close()


async def check_sla_compliance_loop():
    """定期检测工单 SLA 的异步循环（每分钟检查一次）"""
    await asyncio.sleep(10)
    while True:
        try:
            await check_sla_compliance()
        except Exception as e:
            print(f"[SLA Loop] Error: {e}")
        await asyncio.sleep(60)
