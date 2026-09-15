import re
from functools import wraps

from flask import g, jsonify, session
from werkzeug.security import check_password_hash, generate_password_hash

from app.db import db_cursor

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def valid_email(email: str) -> bool:
    return bool(email and EMAIL_RE.match(email.strip()))


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    return check_password_hash(password_hash, password)


def login_user(user_id: int):
    session.clear()
    session["user_id"] = int(user_id)
    session.permanent = True


def logout_user():
    session.clear()


def require_login(fn):
    """网页会话登录。"""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        uid = session.get("user_id")
        if not uid:
            return jsonify(ok=False, error="请先登录"), 401
        with db_cursor() as cur:
            cur.execute(
                "SELECT id, email, status FROM users WHERE id=%s",
                (uid,),
            )
            user = cur.fetchone()
        if not user:
            logout_user()
            return jsonify(ok=False, error="请先登录"), 401
        if user["status"] != 1:
            return jsonify(ok=False, error="账号已禁用"), 403
        g.user = user
        return fn(*args, **kwargs)

    return wrapper
