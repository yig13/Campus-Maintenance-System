import time

from fastapi import APIRouter, Depends

from database import get_db
from auth import require_admin

router = APIRouter()
_STATS_CACHE_SECONDS = 30
_stats_cache = {"expires_at": 0.0, "data": None}


@router.get("/api/stats")
def get_stats(_current_user: dict = Depends(require_admin)):
    now_monotonic = time.monotonic()
    if _stats_cache["data"] is not None and now_monotonic < _stats_cache["expires_at"]:
        return {"success": True, "data": _stats_cache["data"]}

    conn = get_db()

    try:
        repair_counts = conn.execute("""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN status = 'waiting' THEN 1 ELSE 0 END) AS pending,
                   SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) AS in_progress,
                   SUM(CASE WHEN status IN ('pending_evaluation', 'closed') THEN 1 ELSE 0 END) AS completed,
                   SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) AS rejected
            FROM repairs
        """).fetchone()
        total = repair_counts["total"] or 0
        pending = repair_counts["pending"] or 0
        in_progress = repair_counts["in_progress"] or 0
        completed = repair_counts["completed"] or 0
        rejected = repair_counts["rejected"] or 0
        category_rows = conn.execute("SELECT category, COUNT(*) as count FROM repairs GROUP BY category").fetchall()
        building_rows = conn.execute(
            """SELECT dormBuilding as building, COUNT(*) as count
               FROM repairs
               WHERE TRIM(COALESCE(dormBuilding, '')) != ''
               GROUP BY dormBuilding
               ORDER BY count DESC, dormBuilding ASC"""
        ).fetchall()
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        user_count = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'user'").fetchone()[0]
        repairman_count = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'repairman'").fetchone()[0]
        reviews = conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
        avg_rating_row = conn.execute("SELECT AVG(rating) FROM reviews").fetchone()[0]
        trend_query = """
            SELECT date(createdAt) as date, COUNT(*) as count
            FROM repairs
            WHERE createdAt >= date('now', '-7 days')
            GROUP BY date(createdAt)
            ORDER BY date(createdAt) ASC
        """
        trend_rows = conn.execute(trend_query).fetchall()
        trend_data = [{"date": r["date"], "count": r["count"]} for r in trend_rows]

        total_repairs = conn.execute("SELECT COUNT(*) FROM repairs").fetchone()[0]
        breached_query = """
            SELECT COUNT(*) FROM repairs
            WHERE (status IN ('waiting', 'ready', 'in_progress') AND slaDueDate < ?)
               OR (status IN ('pending_evaluation', 'closed') AND updatedAt > slaDueDate)
        """
        now_str = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
        breached_repairs = conn.execute(breached_query, (now_str,)).fetchone()[0]
        sla_compliance_rate = 1.0
        if total_repairs > 0:
            sla_compliance_rate = (total_repairs - breached_repairs) / total_repairs

        avg_response_query = """
            SELECT AVG(julianday(updatedAt) - julianday(createdAt)) * 24 as avg_hours
            FROM repairs
            WHERE status IN ('closed', 'pending_evaluation')
        """
        avg_resp_row = conn.execute(avg_response_query).fetchone()
        avg_response_time = avg_resp_row["avg_hours"] if avg_resp_row and avg_resp_row["avg_hours"] else 0

        total_cost_row = conn.execute("SELECT SUM(rp.quantity * rp.price) FROM repair_parts rp").fetchone()
        total_cost = total_cost_row[0] if total_cost_row and total_cost_row[0] is not None else 0

        parts_consumed_rows = conn.execute("""
            SELECT p.name, SUM(rp.quantity) as count, SUM(rp.quantity * rp.price) as totalCost
            FROM repair_parts rp
            LEFT JOIN parts p ON rp.partId = p.id
            GROUP BY rp.partId
            ORDER BY count DESC
            LIMIT 5
        """).fetchall()
        parts_consumed_stats = [{"name": r["name"] or "已删备件", "count": r["count"], "totalCost": float(f"{r['totalCost']:.2f}")} for r in parts_consumed_rows]
    finally:
        conn.close()

    category_stats = [{"category": r["category"], "count": r["count"]} for r in category_rows]
    building_stats = [{"building": r["building"], "count": r["count"]} for r in building_rows]
    stats_data = {
            "totalRequests": total,
            "pendingRequests": pending,
            "inProgressRequests": in_progress,
            "completedRequests": completed,
            "rejectedRequests": rejected,
            "totalUsers": total_users,
            "userCount": user_count,
            "repairmanCount": repairman_count,
            "categoryStats": category_stats,
            "buildingStats": building_stats,
            "avgRating": f"{avg_rating_row or 0:.1f}",
            "reviewCount": reviews,
            "trendData": trend_data,
            "slaComplianceRate": float(f"{sla_compliance_rate:.4f}"),
            "averageResponseTimeHours": float(f"{avg_response_time:.2f}"),
            "totalCost": float(f"{total_cost:.2f}"),
            "partsConsumedStats": parts_consumed_stats,
        }
    _stats_cache["data"] = stats_data
    _stats_cache["expires_at"] = time.monotonic() + _STATS_CACHE_SECONDS
    return {
        "success": True,
        "data": stats_data,
    }
