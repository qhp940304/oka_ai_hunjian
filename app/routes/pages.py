"""用户端页面路由。"""
from flask import Blueprint, render_template, session

from app.config import Config
from app.services.web_guard import issue_web_token

bp = Blueprint("pages", __name__)


def _ctx(**extra):
    ctx = {
        "site_name": Config.SITE_NAME,
        "logged_in": bool(session.get("user_id")),
        "open_platform_url": "https://kfz.oookay.cn/docs/quickstart",
    }
    ctx.update(extra)
    return ctx


@bp.get("/")
def home():
    return render_template("home.html", **_ctx())


@bp.get("/login")
def login_page():
    token = issue_web_token()
    return render_template("login.html", **_ctx(web_token=token))


@bp.get("/workspace")
def workspace():
    token = issue_web_token()
    return render_template("workspace.html", **_ctx(web_token=token))


@bp.get("/tasks")
def tasks_page():
    return render_template("tasks.html", **_ctx())
