"""网页注册防护：会话令牌、同源校验、蜜罐、IP 限频。"""
from __future__ import annotations

import secrets
import time
from urllib.parse import urlparse

from flask import request, session

from app.config import Config
from app.db import db_cursor

MIN_HUMAN_SECONDS = 2
EMAIL_CODE_PER_IP_HOUR = 8
REGISTER_PER_IP_DAY = 5


def issue_web_token() -> str:
    token = secrets.token_urlsafe(24)
    session["web_reg_token"] = token
    session["web_reg_at"] = int(time.time())
    session.permanent = True
    return token


def _client_ip() -> str:
    forwarded = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    return forwarded or (request.remote_addr or "")


def _host_ok(netloc: str) -> bool:
    if not netloc:
        return False
    host = netloc.lower().split(":")[0]
    req_host = (request.host or "").lower().split(":")[0]
    if host == req_host:
        return True
    base = (Config.PUBLIC_BASE_URL or "").rstrip("/")
    if base:
        pub = urlparse(base).netloc.lower().split(":")[0]
        if host == pub:
            return True
    return False


def _same_site_ok() -> bool:
    site = (request.headers.get("Sec-Fetch-Site") or "").lower()
    if site in ("same-origin", "same-site"):
        return True

    origin = request.headers.get("Origin") or ""
    if origin:
        try:
            if _host_ok(urlparse(origin).netloc):
                return True
        except Exception:
            pass

    referer = request.headers.get("Referer") or ""
    if referer:
        try:
            if _host_ok(urlparse(referer).netloc):
                return True
        except Exception:
            pass
    return False


def _looks_like_browser() -> bool:
    ua = (request.headers.get("User-Agent") or "").strip()
    if len(ua) < 12:
        return False
    bad = (
        "curl/",
        "wget/",
        "python-requests",
        "python-urllib",
        "httpie",
        "scrapy",
        "go-http-client",
        "java/",
        "okhttp",
        "postmanruntime",
        "insomnia",
    )
    low = ua.lower()
    return not any(b in low for b in bad)


def hit_rate_limit(action: str, window_seconds: int, max_count: int) -> bool:
    ip = _client_ip() or "unknown"
    now = int(time.time())
    since = now - window_seconds
    with db_cursor(commit=True) as cur:
        cur.execute(
            """
            SELECT COUNT(*) AS c FROM ip_rate_limits
            WHERE ip=%s AND action=%s AND created_at >= %s
            """,
            (ip, action, since),
        )
        count = int(cur.fetchone()["c"] or 0)
        if count >= max_count:
            return True
        cur.execute(
            "INSERT INTO ip_rate_limits (ip, action, created_at) VALUES (%s, %s, %s)",
            (ip, action, now),
        )
        if now % 50 == 0:
            cur.execute(
                "DELETE FROM ip_rate_limits WHERE created_at < %s",
                (now - 86400 * 2,),
            )
    return False


def guard_web_register(data: dict | None = None, *, consume_token: bool = False):
    data = data or {}

    honeypot = (data.get("website") or data.get("company_url") or "").strip()
    if honeypot:
        return False, "请求被拒绝"

    if not _looks_like_browser():
        return False, "请通过网页注册"

    if not _same_site_ok():
        return False, "请通过网页注册"

    token = (
        request.headers.get("X-Web-Token")
        or data.get("web_token")
        or ""
    ).strip()
    expect = (session.get("web_reg_token") or "").strip()
    if not token or not expect or not secrets.compare_digest(token, expect):
        return False, "页面已过期，请刷新后重试"

    issued_at = int(session.get("web_reg_at") or 0)
    if issued_at and int(time.time()) - issued_at < MIN_HUMAN_SECONDS:
        return False, "操作过快，请稍后再试"

    if consume_token:
        session.pop("web_reg_token", None)
        session.pop("web_reg_at", None)

    return True, None
