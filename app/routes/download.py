"""成片下载：代理开放平台下载接口。"""
import io
import re

from flask import Blueprint, g, jsonify, send_file

from app.auth import require_login
from app.db import db_cursor
from app.services import platform_client
from app.services.platform_client import PlatformError

bp = Blueprint("download", __name__, url_prefix="/api/v1")

JOB_RE = re.compile(r"^job_[A-Za-z0-9]+$")


@bp.get("/tasks/<job_id>/download")
@bp.get("/tasks/<job_id>/download/<int:index>")
@require_login
def download(job_id, index=None):
    if not JOB_RE.match(job_id):
        return jsonify(ok=False, error="job_id 非法"), 400
    if index is None:
        index = 1

    with db_cursor() as cur:
        cur.execute(
            "SELECT id, status FROM tasks WHERE job_id=%s AND user_id=%s",
            (job_id, g.user["id"]),
        )
        row = cur.fetchone()
    if not row:
        return jsonify(ok=False, error="任务不存在"), 404

    try:
        content, mime = platform_client.download_bytes(job_id, index)
    except PlatformError as e:
        code = e.status_code or 502
        payload = {"ok": False, "error": str(e)}
        if code == 410:
            payload["expired"] = True
        return jsonify(**payload), code

    return send_file(
        io.BytesIO(content),
        mimetype=mime or "video/mp4",
        as_attachment=True,
        download_name=f"{job_id}_{index}.mp4",
    )
