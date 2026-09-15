import time as _time

from flask import Blueprint, g, jsonify, request

from app.auth import (
    hash_password,
    login_user,
    logout_user,
    require_login,
    valid_email,
    verify_password,
)
from app.db import db_cursor
from app.services.email_service import send_email_code, verify_email_code
from app.services.web_guard import (
    EMAIL_CODE_PER_IP_HOUR,
    REGISTER_PER_IP_DAY,
    _client_ip,
    guard_web_register,
    hit_rate_limit,
    issue_web_token,
)

bp = Blueprint("auth", __name__, url_prefix="/api/v1")


@bp.get("/web/challenge")
def web_challenge():
    from app.services.web_guard import _looks_like_browser, _same_site_ok

    if not (_looks_like_browser() and _same_site_ok()):
        return jsonify(ok=False, error="请通过网页注册"), 403
    token = issue_web_token()
    return jsonify(ok=True, web_token=token)


@bp.post("/email/code")
def email_code():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    event = (data.get("event") or "register").strip()
    if not valid_email(email):
        return jsonify(ok=False, error="邮箱格式不正确"), 400

    if event == "register":
        ok, err = guard_web_register(data)
        if not ok:
            return jsonify(ok=False, error=err), 403
        if hit_rate_limit("email_code", 3600, EMAIL_CODE_PER_IP_HOUR):
            return jsonify(ok=False, error="发送过于频繁，请稍后再试"), 429
    else:
        return jsonify(ok=False, error="不支持的事件类型"), 400

    ok, msg = send_email_code(email, event, request.remote_addr or "")
    if not ok:
        return jsonify(ok=False, error=msg), 400
    return jsonify(ok=True, message=msg)


@bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    code = (data.get("code") or data.get("captcha") or "").strip()

    ok, err = guard_web_register(data, consume_token=False)
    if not ok:
        return jsonify(ok=False, error=err), 403

    if not valid_email(email):
        return jsonify(ok=False, error="邮箱格式不正确"), 400
    if len(password) < 6:
        return jsonify(ok=False, error="密码至少 6 位"), 400
    if not code:
        return jsonify(ok=False, error="请输入邮箱验证码"), 400

    ok, msg = verify_email_code(email, code, "register")
    if not ok:
        return jsonify(ok=False, error=msg), 400

    ip = _client_ip() or "unknown"
    now = int(_time.time())
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) AS c FROM ip_rate_limits
            WHERE ip=%s AND action='register' AND created_at >= %s
            """,
            (ip, now - 86400),
        )
        if int(cur.fetchone()["c"] or 0) >= REGISTER_PER_IP_DAY:
            return jsonify(ok=False, error="今日注册次数已达上限，请明天再试"), 429

    pwd_hash = hash_password(password)

    try:
        with db_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO users (email, password_hash)
                VALUES (%s, %s)
                """,
                (email, pwd_hash),
            )
            user_id = cur.lastrowid
            cur.execute(
                "INSERT INTO ip_rate_limits (ip, action, created_at) VALUES (%s, %s, %s)",
                (ip, "register", now),
            )
    except Exception as e:
        if "Duplicate" in str(e) or "1062" in str(e):
            return jsonify(ok=False, error="该邮箱已注册"), 409
        raise

    login_user(user_id)
    issue_web_token()

    return jsonify(
        ok=True,
        message="注册成功",
        user={"id": user_id, "email": email},
    )


@bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not email or not password:
        return jsonify(ok=False, error="请输入邮箱和密码"), 400

    with db_cursor() as cur:
        cur.execute(
            "SELECT id, email, password_hash, status FROM users WHERE email=%s",
            (email,),
        )
        user = cur.fetchone()

    if not user or not verify_password(user["password_hash"], password):
        return jsonify(ok=False, error="邮箱或密码错误"), 401
    if user["status"] != 1:
        return jsonify(ok=False, error="账号已禁用"), 403

    login_user(user["id"])
    return jsonify(
        ok=True,
        user={"id": user["id"], "email": user["email"]},
    )


@bp.post("/logout")
def logout():
    logout_user()
    return jsonify(ok=True, message="已退出登录")


@bp.get("/me")
@require_login
def me():
    return jsonify(
        ok=True,
        user={"id": g.user["id"], "email": g.user["email"]},
    )
