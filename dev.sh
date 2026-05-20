#!/bin/bash
set -euo pipefail

echo "===== 开发环境启动 ====="

# ---------- 1. 同步配置 ----------
echo ""
echo "[1/5] 同步配置..."
cp .env.dev .env

# ---------- 2. 安装依赖 ----------
echo ""
echo "[2/5] 安装依赖..."
uv sync --all-extras

# ---------- 3. 启动数据库 ----------
echo ""
echo "[3/5] 启动数据库..."
docker compose up -d

# ---------- 4. 执行数据库迁移 ----------
echo ""
echo "[4/5] 执行数据库迁移..."
uv run alembic upgrade head

# ---------- 5. 启动服务 ----------
echo ""
echo "[5/5] 启动服务..."
uv run fastapi run app/main.py --reload
