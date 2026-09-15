"""素材上传：优先转发到开放平台，失败时回退为本地静态托管。"""
from __future__ import annotations

import secrets
import time
from pathlib import Path

from flask import Blueprint, g, jsonify, request
from werkzeug.utils import secure_filename

from app.auth import require_login
from app.config import BASE_DIR, Config
from app.services import platform_client
from app.services.platform_client import PlatformError

bp = Blueprint("upload", __name__, url_prefix="/api/v1")

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv", ".avi"}
MAX_IMAGE = 15 * 1024 * 1024
MAX_VIDEO = 200 * 1024 * 1024


def _public_base() -> str:
    base = (Config.PUBLIC_BASE_URL or "").rstrip("/")
    if base:
        return base
    return (request.url_root or "").rstrip("/")


@bp.post("/upload/materials")
@require_login
def upload_materials():
    kind = (request.form.get("kind") or "auto").strip().lower()
    files = request.files.getlist("files") or request.files.getlist("file")
    if not files:
        single = request.files.get("file")
        files = [single] if single else []
    files = [f for f in files if f and f.filename]
    if not files:
        return jsonify(ok=False, error="请选择要上传的文件"), 400
    if len(files) > 20:
        return jsonify(ok=False, error="单次最多上传 20 个文件"), 400

    prepared = []
    errors = []
    for f in files:
        name = secure_filename(f.filename) or "file"
        ext = Path(name).suffix.lower()
        raw = f.read()
        if not raw:
            errors.append("%s: 空文件" % name)
            continue

        file_kind = kind
        if file_kind == "auto":
            if ext in IMAGE_EXT:
                file_kind = "image"
            elif ext in VIDEO_EXT:
                file_kind = "video"
            else:
                errors.append("%s: 不支持的格式" % name)
                continue

        if file_kind == "image":
            if ext not in IMAGE_EXT:
                errors.append("%s: 不是图片格式" % name)
                continue
            if len(raw) > MAX_IMAGE:
                errors.append("%s: 图片超过 15MB" % name)
                continue
        elif file_kind == "video":
            if ext not in VIDEO_EXT:
                errors.append("%s: 不是视频格式" % name)
                continue
            if len(raw) > MAX_VIDEO:
                errors.append("%s: 视频超过 200MB" % name)
                continue
        else:
            errors.append("%s: kind 无效" % name)
            continue

        ctype = f.mimetype or (
            "image/jpeg" if file_kind == "image" else "video/mp4"
        )
        prepared.append((name, raw, ctype, file_kind, ext))

    if not prepared:
        return jsonify(ok=False, error=errors[0] if errors else "上传失败"), 400

    # 优先上传到开放平台，获得其可访问的素材 URL
    try:
        tuples = [(n, raw, ct) for n, raw, ct, _, _ in prepared]
        remote = platform_client.upload_materials(
            tuples, kind=kind if kind in ("image", "video") else "auto"
        )
        return jsonify(
            ok=True,
            images=remote.get("images") or [],
            videos=remote.get("videos") or [],
            errors=errors or remote.get("errors"),
            message="上传成功",
        )
    except PlatformError:
        pass

    # 回退：存本站静态目录（需 PUBLIC_BASE_URL 可被开放平台访问）
    upload_root = BASE_DIR / "static" / "uploads" / "materials" / str(g.user["id"])
    upload_root.mkdir(parents=True, exist_ok=True)
    images = []
    videos = []
    for name, raw, _ctype, file_kind, ext in prepared:
        filename = "%d_%s%s" % (int(time.time() * 1000), secrets.token_hex(4), ext)
        dest = upload_root / filename
        dest.write_bytes(raw)
        url = "%s/static/uploads/materials/%s/%s" % (
            _public_base(),
            g.user["id"],
            filename,
        )
        item = {"name": name, "url": url, "size": len(raw)}
        if file_kind == "image":
            images.append(item)
        else:
            videos.append(item)

    return jsonify(
        ok=True,
        images=images,
        videos=videos,
        errors=errors or None,
        message="上传成功",
    )
