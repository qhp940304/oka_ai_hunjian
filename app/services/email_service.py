"""邮箱验证码（SMTP）。"""
from __future__ import annotations

import html
import random
import smtplib
import time
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from app.config import Config
from app.db import db_cursor


def _gen_code():
    return "%06d" % random.randint(0, 999999)


def _event_label(event):
    return {
        "register": "注册账号",
        "login": "登录验证",
    }.get(event, "身份验证")


def _site_url():
    return (Config.PUBLIC_BASE_URL or "").rstrip("/")


def _build_code_email(code, event):
    minutes = max(1, Config.CODE_EXPIRE // 60)
    site = Config.SITE_NAME
    action = _event_label(event)
    code_safe = html.escape(str(code))
    site_safe = html.escape(site)
    action_safe = html.escape(action)
    site_url = html.escape(_site_url())

    plain = (
        "【%s】验证码\n\n"
        "您正在进行「%s」操作。\n"
        "验证码：%s\n"
        "有效期：%d 分钟\n\n"
        "如非本人操作，请忽略本邮件。\n"
        "%s"
    ) % (site, action, code, minutes, _site_url() or "")

    html_body = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>%(site)s 验证码</title>
</head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;">
  <table role="presentation" width="100%%" cellspacing="0" cellpadding="0" border="0" style="background:#f4f6f9;padding:32px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%%" cellspacing="0" cellpadding="0" border="0" style="max-width:520px;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 8px 28px rgba(20,28,45,0.08);">
          <tr>
            <td style="background:linear-gradient(135deg,#fe2c55,#ff6a3d);padding:28px 24px;text-align:center;">
              <div style="font-size:22px;font-weight:700;color:#ffffff;letter-spacing:0.02em;">%(site)s</div>
              <div style="margin-top:6px;font-size:13px;color:rgba(255,255,255,0.9);">邮箱验证</div>
            </td>
          </tr>
          <tr>
            <td style="padding:32px 28px 12px;text-align:center;">
              <div style="font-size:18px;font-weight:700;color:#141c2b;margin-bottom:8px;">邮箱验证码</div>
              <div style="font-size:14px;color:#6b7385;line-height:1.6;">
                您正在进行「%(action)s」操作，请使用下方验证码完成验证。
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 28px 20px;" align="center">
              <div style="display:inline-block;background:#fff1f4;border:1px dashed rgba(254,44,85,0.45);border-radius:12px;padding:16px 28px;">
                <div style="font-size:12px;color:#9aa3b2;margin-bottom:6px;letter-spacing:0.08em;">VERIFICATION CODE</div>
                <div style="font-size:36px;font-weight:700;letter-spacing:0.28em;color:#fe2c55;font-family:Consolas,'Courier New',monospace;">%(code)s</div>
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding:0 28px 28px;text-align:center;">
              <div style="font-size:13px;color:#8a92a3;line-height:1.7;">
                验证码 <strong style="color:#fe2c55;">%(minutes)d 分钟</strong> 内有效，请勿泄露给他人。<br>
                如非本人操作，请忽略本邮件。
              </div>
            </td>
          </tr>
          <tr>
            <td style="background:#fafbfc;border-top:1px solid #eef1f5;padding:16px 24px;text-align:center;">
              <a href="%(site_url)s" style="color:#fe2c55;text-decoration:none;font-size:13px;font-weight:600;">访问 %(site)s</a>
              <div style="margin-top:8px;font-size:11px;color:#b0b7c3;">本邮件由系统自动发送，请勿直接回复</div>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>""" % {
        "site": site_safe,
        "action": action_safe,
        "code": code_safe,
        "minutes": minutes,
        "site_url": site_url or "#",
    }
    return plain, html_body


def send_email_code(email, event, ip=""):
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        return False, "请输入正确的邮箱"

    if event not in ("register", "login"):
        return False, "无效的事件类型"

    if event == "register":
        with db_cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email=%s", (email,))
            if cur.fetchone():
                return False, "该邮箱已注册"

    now = int(time.time())
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT id, createtime FROM email_codes
            WHERE email=%s AND event=%s ORDER BY id DESC LIMIT 1
            """,
            (email, event),
        )
        recent = cur.fetchone()
    if recent and now - int(recent["createtime"]) < 60:
        return False, "发送过于频繁，请稍后再试"

    code = _gen_code()
    with db_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO email_codes (email, code, event, times, ip, createtime, expiretime)
            VALUES (%s, %s, %s, 0, %s, %s, %s)
            """,
            (email, code, event, ip or "", now, now + Config.CODE_EXPIRE),
        )

    subject = "【%s】%s验证码" % (Config.SITE_NAME, _event_label(event))
    plain, html_body = _build_code_email(code, event)
    sent = _smtp_send(email, subject, plain, html_body)
    if not sent:
        if Config.SMTP_HOST and Config.SMTP_USER:
            print("[EMAIL CODE FALLBACK] %s event=%s code=%s" % (email, event, code))
            return False, "邮件发送失败，请稍后重试"
        print("[EMAIL CODE] %s event=%s code=%s" % (email, event, code))

    msg = "验证码已发送"
    if Config.DEV_SHOW_CODE:
        msg = "验证码已发送（开发模式：%s）" % code
    return True, msg


def verify_email_code(email, code, event):
    email = (email or "").strip().lower()
    code = (code or "").strip()
    if not email or not code:
        return False, "请输入邮箱和验证码"

    now = int(time.time())
    with db_cursor(commit=True) as cur:
        cur.execute(
            """
            SELECT * FROM email_codes
            WHERE email=%s AND event=%s AND code=%s
            ORDER BY id DESC LIMIT 1
            """,
            (email, event, code),
        )
        row = cur.fetchone()
        if not row:
            return False, "验证码错误"
        if int(row["expiretime"]) < now:
            return False, "验证码已过期"
        if int(row["times"]) >= 10:
            return False, "验证码已失效，请重新获取"
        cur.execute(
            "UPDATE email_codes SET times=times+1 WHERE id=%s",
            (row["id"],),
        )
    return True, "ok"


def _smtp_send(to_email, subject, plain_body, html_body=None):
    if not Config.SMTP_HOST or not Config.SMTP_USER:
        return False
    try:
        from_addr = (Config.SMTP_FROM or Config.SMTP_USER or "").strip()
        sender_name = (Config.SMTP_SENDER_NAME or Config.SITE_NAME or "").strip()

        if html_body:
            msg = MIMEMultipart("alternative")
            msg.attach(MIMEText(plain_body, "plain", "utf-8"))
            msg.attach(MIMEText(html_body, "html", "utf-8"))
        else:
            msg = MIMEText(plain_body, "plain", "utf-8")

        msg["From"] = formataddr((sender_name, from_addr))
        msg["To"] = to_email
        msg["Subject"] = Header(subject, "utf-8")

        if Config.SMTP_SSL:
            server = smtplib.SMTP_SSL(Config.SMTP_HOST, Config.SMTP_PORT, timeout=15)
        else:
            server = smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT, timeout=15)
            server.starttls()
        server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
        server.sendmail(from_addr, [to_email], msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print("[SMTP ERROR]", e)
        return False
