"""站点运行时配置（KV）。"""
from __future__ import annotations

from app.config import Config
from app.db import db_cursor


def get_config_map():
    with db_cursor() as cur:
        cur.execute("SELECT `key`, `value` FROM app_config")
        rows = cur.fetchall()
    data = {r["key"]: r["value"] for r in rows}
    return data


def set_config(key: str, value: str):
    with db_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO app_config (`key`, `value`) VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE `value`=VALUES(`value`)
            """,
            (key, value),
        )
