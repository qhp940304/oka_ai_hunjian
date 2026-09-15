"""独立数据库建表（用户端：账号与任务记录）。"""
from __future__ import annotations

import pymysql
from pymysql.cursors import DictCursor

from app.config import Config

TABLE_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS app_config (
      `key`   VARCHAR(64)  NOT NULL PRIMARY KEY,
      `value` TEXT         NOT NULL,
      updated_at DATETIME  NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS users (
      id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
      email         VARCHAR(191)    NOT NULL,
      password_hash VARCHAR(255)    NOT NULL,
      status        TINYINT         NOT NULL DEFAULT 1,
      created_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      UNIQUE KEY uk_email (email)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS tasks (
      id                 BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
      user_id            BIGINT UNSIGNED NOT NULL,
      job_id             VARCHAR(64)     NOT NULL COMMENT '开放平台任务 ID',
      images_json        JSON            NOT NULL,
      videos_json        JSON            NOT NULL,
      status             VARCHAR(16)     NOT NULL DEFAULT 'pending',
      boost              TINYINT         NOT NULL DEFAULT 0,
      error              TEXT            NULL,
      export_count       INT             NOT NULL DEFAULT 0,
      result_json        JSON            NULL,
      expires_at         DATETIME        NULL,
      created_at         DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at         DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      finished_at        DATETIME        NULL,
      UNIQUE KEY uk_job_id (job_id),
      KEY idx_user_created (user_id, created_at),
      KEY idx_status (status),
      CONSTRAINT fk_c_task_user FOREIGN KEY (user_id) REFERENCES users(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS email_codes (
      id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
      email      VARCHAR(191)    NOT NULL,
      code       VARCHAR(16)     NOT NULL,
      event      VARCHAR(32)     NOT NULL,
      times      INT             NOT NULL DEFAULT 0,
      ip         VARCHAR(64)     NULL,
      createtime INT UNSIGNED    NOT NULL,
      expiretime INT UNSIGNED    NOT NULL,
      KEY idx_email_event (email, event),
      KEY idx_expire (expiretime)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS ip_rate_limits (
      id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
      ip         VARCHAR(64)     NOT NULL,
      action     VARCHAR(32)     NOT NULL,
      created_at INT UNSIGNED    NOT NULL,
      KEY idx_ip_action_time (ip, action, created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
]


def _server_connection():
    return pymysql.connect(
        host=Config.MYSQL_HOST,
        port=Config.MYSQL_PORT,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=True,
    )


def _db_connection():
    return pymysql.connect(
        host=Config.MYSQL_HOST,
        port=Config.MYSQL_PORT,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DATABASE,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=True,
    )


def ensure_database():
    db_name = Config.MYSQL_DATABASE
    conn = _server_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                "DEFAULT CHARACTER SET utf8mb4 "
                "DEFAULT COLLATE utf8mb4_unicode_ci"
            )
    finally:
        conn.close()


def ensure_tables(cur):
    for sql in TABLE_STATEMENTS:
        cur.execute(sql)
    _ensure_legacy_compat(cur)


def _column_exists(cur, table: str, column: str) -> bool:
    cur.execute(
        """
        SELECT COUNT(*) AS c FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME=%s
        """,
        (Config.MYSQL_DATABASE, table, column),
    )
    return int(cur.fetchone()["c"] or 0) > 0


def _ensure_legacy_compat(cur):
    """兼容旧库遗留字段，避免插入报错。"""
    if _column_exists(cur, "tasks", "client_id"):
        try:
            cur.execute(
                "ALTER TABLE tasks MODIFY COLUMN client_id VARCHAR(128) NULL DEFAULT NULL"
            )
        except Exception:
            pass
    if _column_exists(cur, "tasks", "points_cost"):
        try:
            cur.execute(
                "ALTER TABLE tasks MODIFY COLUMN points_cost INT NOT NULL DEFAULT 0"
            )
        except Exception:
            pass
    if _column_exists(cur, "users", "points"):
        try:
            cur.execute(
                "ALTER TABLE users MODIFY COLUMN points INT NOT NULL DEFAULT 0"
            )
        except Exception:
            pass


def seed_default_config(cur):
    defaults = [
        ("site_tagline", "上传素材，AI 生成短视频成片"),
    ]
    for key, value in defaults:
        cur.execute(
            """
            INSERT INTO app_config (`key`, `value`) VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE `key`=`key`
            """,
            (key, value),
        )


def init_db(create_database: bool = True):
    if create_database:
        try:
            ensure_database()
        except pymysql.err.OperationalError as e:
            print(f"[schema] 跳过建库（将使用已有库 {Config.MYSQL_DATABASE}）: {e}")

    conn = _db_connection()
    try:
        with conn.cursor() as cur:
            ensure_tables(cur)
            seed_default_config(cur)
        print(
            f"[schema] 数据表已就绪 database={Config.MYSQL_DATABASE} "
            f"host={Config.MYSQL_HOST}"
        )
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
