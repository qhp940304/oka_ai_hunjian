"""成片任务：调用开放平台 API（扣费由开放平台账户承担）。"""
from __future__ import annotations

import json
import re
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from app.auth import require_login
from app.db import db_cursor
from app.services import platform_client
from app.services.platform_client import PlatformError

bp = Blueprint("tasks", __name__, url_prefix="/api/v1")

URL_RE = re.compile(r"^https?://", re.I)


def _truthy(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "on")
    return False


def _parse_expires(val):
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    s = str(val).replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.strptime(s[:26], fmt)
        except ValueError:
            continue
    return None


def _validate_materials(data):
    images = data.get("images") or []
    videos = data.get("videos") or []
    if not isinstance(images, list):
        images = []
    if not isinstance(videos, list):
        videos = []
    images = [str(u).strip() for u in images if str(u).strip()]
    videos = [str(u).strip() for u in videos if str(u).strip()]
    if not images and not videos:
        return None, "images 与 videos 至少提供一个非空列表"
    for u in images + videos:
        if not URL_RE.match(u):
            return None, f"素材链接须为 http/https: {u}"
    boost = _truthy(data.get("boost") if data.get("boost") is not None else data.get("accelerate"))
    return {"images": images, "videos": videos, "boost": boost}, None


def _apply_remote_job(cur, row, job: dict):
    status = (job.get("status") or row["status"] or "").strip()
    export_count = int(job.get("export_count") or 0)
    error = job.get("error")
    expires_at = _parse_expires(job.get("expires_at"))
    finished_at = None
    if status in ("success", "failed"):
        finished_at = datetime.now()

    cur.execute(
        """
        UPDATE tasks
        SET status=%s, export_count=%s, error=%s, result_json=%s,
            expires_at=%s,
            finished_at=IFNULL(finished_at, %s),
            updated_at=NOW()
        WHERE id=%s
        """,
        (
            status,
            export_count,
            error,
            json.dumps(job, ensure_ascii=False),
            expires_at,
            finished_at,
            row["id"],
        ),
    )
    row["status"] = status
    row["export_count"] = export_count
    row["error"] = error
    row["expires_at"] = expires_at
    row["result_json"] = job
    return row


def _sync_task(row):
    if not row or not row.get("job_id"):
        return row
    try:
        job = platform_client.get_task(row["job_id"])
    except PlatformError:
        return row
    with db_cursor(commit=True) as cur:
        cur.execute("SELECT * FROM tasks WHERE id=%s FOR UPDATE", (row["id"],))
        locked = cur.fetchone() or row
        return _apply_remote_job(cur, locked, job)


def _task_to_public(row):
    images = row.get("images_json")
    videos = row.get("videos_json")
    if isinstance(images, str):
        images = json.loads(images)
    if isinstance(videos, str):
        videos = json.loads(videos)

    remote = row.get("result_json")
    if isinstance(remote, str):
        try:
            remote = json.loads(remote)
        except (TypeError, ValueError, json.JSONDecodeError):
            remote = {}
    remote = remote or {}

    status = row.get("status") or remote.get("status") or "pending"
    export_count = int(row.get("export_count") or remote.get("export_count") or 0)
    expired = bool(remote.get("expired"))
    expires_at = row.get("expires_at") or remote.get("expires_at")
    expires_str = (
        expires_at.isoformat(sep=" ")
        if hasattr(expires_at, "isoformat")
        else (str(expires_at) if expires_at else None)
    )

    download_urls = []
    if status == "success" and export_count > 0 and not expired:
        for i in range(1, export_count + 1):
            download_urls.append(f"/api/v1/tasks/{row['job_id']}/download/{i}")

    return {
        "job_id": row["job_id"],
        "status": status,
        "images": images or [],
        "videos": videos or [],
        "export_count": export_count,
        "created_at": row["created_at"].isoformat(sep=" ") if row.get("created_at") else None,
        "updated_at": row["updated_at"].isoformat(sep=" ") if row.get("updated_at") else None,
        "finished_at": row["finished_at"].isoformat(sep=" ") if row.get("finished_at") else None,
        "expires_at": expires_str,
        "expired": expired,
        "boost": bool(row.get("boost")),
        "error": row.get("error") or remote.get("error"),
        "download_url": download_urls[0] if download_urls else None,
        "download_urls": download_urls or None,
        "queue_ahead": remote.get("queue_ahead"),
        "queue_message": remote.get("queue_message"),
    }


@bp.post("/tasks")
@require_login
def create_task():
    data = request.get_json(silent=True) or {}
    payload, err = _validate_materials(data)
    if err:
        return jsonify(ok=False, error=err), 400

    user_id = g.user["id"]

    try:
        remote = platform_client.create_task(
            payload["images"], payload["videos"], boost=payload["boost"]
        )
    except PlatformError as e:
        return jsonify(ok=False, error=str(e)), e.status_code or 502

    job_id = remote.get("job_id")
    if not job_id:
        return jsonify(ok=False, error="开放平台未返回 job_id"), 502

    with db_cursor(commit=True) as cur:
        # 兼容旧库遗留字段（client_id / points_cost）
        def _has_col(name: str) -> bool:
            cur.execute(
                """
                SELECT COUNT(*) AS c FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='tasks' AND COLUMN_NAME=%s
                """,
                (name,),
            )
            return int((cur.fetchone() or {}).get("c") or 0) > 0

        cols = ["user_id", "job_id"]
        vals = [user_id, job_id]
        if _has_col("client_id"):
            cols.append("client_id")
            vals.append(str(user_id))
        cols.extend(["images_json", "videos_json", "status", "boost"])
        vals.extend(
            [
                json.dumps(payload["images"], ensure_ascii=False),
                json.dumps(payload["videos"], ensure_ascii=False),
                remote.get("status") or "pending",
                1 if payload["boost"] else 0,
            ]
        )
        if _has_col("points_cost"):
            cols.append("points_cost")
            vals.append(0)
        cols.append("result_json")
        vals.append(json.dumps(remote, ensure_ascii=False))

        placeholders = ", ".join(["%s"] * len(vals))
        cur.execute(
            f"INSERT INTO tasks ({', '.join(cols)}) VALUES ({placeholders})",
            tuple(vals),
        )

    return jsonify(
        ok=True,
        job_id=job_id,
        status=remote.get("status") or "pending",
        boost=payload["boost"],
        queue_ahead=remote.get("queue_ahead"),
        queue_message=remote.get("queue_message") or "任务已提交",
        status_url=f"/api/v1/tasks/{job_id}",
        message="任务已受理",
    )


@bp.get("/tasks/<job_id>")
@require_login
def get_task(job_id):
    with db_cursor() as cur:
        cur.execute(
            "SELECT * FROM tasks WHERE job_id=%s AND user_id=%s",
            (job_id, g.user["id"]),
        )
        row = cur.fetchone()
    if not row:
        return jsonify(ok=False, error="任务不存在"), 404
    row = _sync_task(row)
    return jsonify(ok=True, job=_task_to_public(row))


@bp.get("/tasks")
@require_login
def list_tasks():
    limit = min(int(request.args.get("limit", 20)), 100)
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT * FROM tasks WHERE user_id=%s
            ORDER BY id DESC LIMIT %s
            """,
            (g.user["id"], limit),
        )
        rows = cur.fetchall() or []

    out = []
    for row in rows:
        if row.get("status") in ("pending", "running", "success"):
            row = _sync_task(row)
        out.append(_task_to_public(row))
    return jsonify(ok=True, tasks=out)


@bp.get("/queue")
@require_login
def my_queue():
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT * FROM tasks
            WHERE user_id=%s AND status IN ('pending', 'running')
            ORDER BY id DESC LIMIT 1
            """,
            (g.user["id"],),
        )
        row = cur.fetchone()
    if not row:
        return jsonify(
            ok=True,
            has_active=False,
            queue_ahead=None,
            message="当前没有排队中的任务",
        )
    row = _sync_task(row)
    pub = _task_to_public(row)
    return jsonify(
        ok=True,
        has_active=True,
        job_id=row["job_id"],
        status=pub["status"],
        queue_ahead=pub.get("queue_ahead"),
        queue_message=pub.get("queue_message") or (
            "正在处理中" if pub["status"] == "running" else "排队中"
        ),
    )
