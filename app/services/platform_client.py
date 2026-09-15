"""开放平台 HTTP 客户端：成片任务创建、查询与下载。"""
from __future__ import annotations

import requests

from app.config import Config

_platform_user_id = None


class PlatformError(Exception):
    def __init__(self, message, status_code=None, payload=None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload or {}


def _base() -> str:
    return Config.OPEN_PLATFORM_BASE_URL.rstrip("/")


def _headers() -> dict:
    key = Config.OPEN_PLATFORM_API_KEY
    if not key:
        raise PlatformError("未配置 OPEN_PLATFORM_API_KEY")
    return {
        "X-API-Key": key,
        "Content-Type": "application/json",
    }


def _request(method: str, path: str, **kwargs):
    url = f"{_base()}/api/v1{path}"
    timeout = kwargs.pop("timeout", 60)
    headers = kwargs.pop("headers", {})
    merged = _headers()
    merged.update(headers)
    # 上传时不要强行 JSON Content-Type
    if kwargs.get("files") or kwargs.get("data") is not None and "json" not in kwargs:
        merged.pop("Content-Type", None)
    try:
        resp = requests.request(
            method, url, headers=merged, timeout=timeout, **kwargs
        )
    except requests.RequestException as e:
        raise PlatformError(f"开放平台不可用: {e}") from e

    try:
        data = resp.json() if resp.content else {}
    except ValueError:
        data = {"raw": (resp.text or "")[:300]}

    if not resp.ok or (isinstance(data, dict) and data.get("ok") is False):
        err = ""
        if isinstance(data, dict):
            err = data.get("error") or data.get("message") or ""
        raise PlatformError(
            err or f"开放平台请求失败 HTTP {resp.status_code}",
            status_code=resp.status_code,
            payload=data if isinstance(data, dict) else {},
        )
    return data


def get_me():
    return _request("GET", "/me")


def platform_user_id() -> str:
    """创建任务所需的开放平台用户 id（与 API Key 绑定）。"""
    global _platform_user_id
    if _platform_user_id:
        return str(_platform_user_id)
    data = get_me()
    user = data.get("user") or {}
    uid = user.get("id")
    if uid is None:
        raise PlatformError("开放平台未返回用户 id")
    _platform_user_id = uid
    return str(uid)


def create_task(images, videos, boost=False):
    payload = {
        "id": platform_user_id(),
        "images": images or [],
        "videos": videos or [],
        "boost": bool(boost),
    }
    return _request("POST", "/tasks", json=payload, timeout=60)


def get_task(job_id: str):
    data = _request("GET", f"/tasks/{job_id}", timeout=30)
    return data.get("job") or data


def list_tasks(limit: int = 20):
    data = _request("GET", f"/tasks?limit={int(limit)}", timeout=30)
    return data.get("tasks") or []


def upload_materials(file_tuples, kind: str = "auto"):
    """
    转发素材到开放平台。
    file_tuples: [(filename, bytes, content_type), ...]
    """
    key = Config.OPEN_PLATFORM_API_KEY
    if not key:
        raise PlatformError("未配置 OPEN_PLATFORM_API_KEY")
    url = f"{_base()}/api/v1/upload/materials"
    files = []
    for name, raw, ctype in file_tuples:
        files.append(("files", (name, raw, ctype or "application/octet-stream")))
    try:
        resp = requests.post(
            url,
            headers={"X-API-Key": key},
            data={"kind": kind},
            files=files,
            timeout=180,
        )
    except requests.RequestException as e:
        raise PlatformError(f"开放平台上传失败: {e}") from e
    try:
        data = resp.json() if resp.content else {}
    except ValueError:
        raise PlatformError(f"开放平台上传返回非 JSON HTTP {resp.status_code}")
    if not resp.ok or not data.get("ok"):
        raise PlatformError(
            data.get("error") or f"上传失败 HTTP {resp.status_code}",
            status_code=resp.status_code,
            payload=data,
        )
    return data


def download_bytes(job_id: str, index: int = 1):
    """拉取成片二进制内容。"""
    key = Config.OPEN_PLATFORM_API_KEY
    if not key:
        raise PlatformError("未配置 OPEN_PLATFORM_API_KEY")
    url = f"{_base()}/api/v1/tasks/{job_id}/download/{int(index)}"
    try:
        resp = requests.get(
            url,
            headers={"X-API-Key": key},
            timeout=300,
            stream=True,
        )
    except requests.RequestException as e:
        raise PlatformError(f"下载失败: {e}") from e

    if resp.status_code == 410:
        raise PlatformError("成片已过期", status_code=410)
    if not resp.ok:
        try:
            data = resp.json()
            err = data.get("error") or f"下载失败 HTTP {resp.status_code}"
        except ValueError:
            err = f"下载失败 HTTP {resp.status_code}"
        raise PlatformError(err, status_code=resp.status_code)

    return resp.content, resp.headers.get("Content-Type", "video/mp4")
