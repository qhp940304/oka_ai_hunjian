# OKA · C 端用户站

面向普通用户的 AI 短视频生成网站：邮箱注册登录、上传素材生成成片。

成片能力通过 [开放平台 API](https://kfz.oookay.cn/docs) 调用。额度与计费请在开放平台自行查看与管理。

## 功能

- 邮箱注册 / 登录
- 上传图片 / 短视频，提交生成任务（可选加速）
- 作品列表、状态查询、下载成片

## 技术栈

- Python 3.10+ / Flask
- MySQL 8
- Jinja2 + 原生 JS

## 架构说明

```
用户浏览器 → 本站（账号 / 页面）
                ↓  X-API-Key
           开放平台 API（成片任务 / 下载）
```

请在 `.env` 中配置：

| 变量 | 说明 |
|------|------|
| `OPEN_PLATFORM_BASE_URL` | 默认 `https://kfz.oookay.cn` |
| `OPEN_PLATFORM_API_KEY` | 开放平台控制台申请的 API Key |

## 快速开始

```bash
cd C端网站
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
# source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# 编辑 .env：MySQL、SMTP、OPEN_PLATFORM_API_KEY、PUBLIC_BASE_URL 等
```

启动：

```bash
python run.py
```

默认端口 `5100`。

## 目录

```
app/           Flask 应用
templates/     页面
static/        样式与脚本
run.py         启动入口
```

## 开源注意

- 不要把真实的 `OPEN_PLATFORM_API_KEY`、数据库密码、SMTP 授权码提交到 GitHub
- `.env` 已在 `.gitignore` 中，请使用 `.env.example` 作为模板
