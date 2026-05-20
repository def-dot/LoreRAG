#!/bin/bash
set -euo pipefail

ENV=${1:-prod}
ENV_FILE=".env.${ENV}"

if [ ! -f "$ENV_FILE" ]; then
    echo "!!! 配置文件 $ENV_FILE 不存在 !!!"
    echo "用法: bash deploy.sh [prod|staging]"
    exit 1
fi

COMPOSE_FILES="-f compose.yml -f compose.prod.yml"
DC="docker compose $COMPOSE_FILES"

echo "===== ${ENV} 环境部署 ====="

# ---------- 1. 同步配置 ----------
echo ""
echo "[1/7] 同步配置..."
cp "$ENV_FILE" .env

# ---------- 2. 拉取最新镜像 ----------
echo ""
echo "[2/7] 拉取最新镜像..."
$DC pull backend db_migrate || true

# ---------- 3. 启动数据库 ----------
echo ""
echo "[3/7] 启动数据库..."
$DC up -d db

# ---------- 4. 备份数据库 ----------
echo ""
echo "[4/7] 备份数据库..."
$DC up -d db_backup
$DC exec db_backup /usr/local/bin/backup.sh

# ---------- 5. 执行数据库迁移 ----------
echo ""
echo "[5/7] 执行数据库迁移..."
if ! $DC run --rm db_migrate; then
    echo ""
    echo "!!! 迁移失败 !!!"
    echo "恢复步骤："
    echo "  1. 查看最新备份： ls -lt db_backup/"
    echo "  2. 恢复数据库：   gunzip -c db_backup/db_XXX.sql.gz | $DC exec -T db psql -U postgres fastapi_template"
    echo "  3. 回退镜像版本： 修改 .env.${ENV} 中 DOCKER_TAG 为上一版本，重新执行 bash deploy.sh ${ENV}"
    exit 1
fi

# ---------- 6. 启动服务 ----------
echo ""
echo "[6/7] 启动服务..."
$DC up -d

# ---------- 7. 健康检查 ----------
echo ""
echo "[7/7] 健康检查..."
HEALTH_URL="http://localhost/health"
MAX_RETRIES=30
for i in $(seq 1 $MAX_RETRIES); do
    if curl -sf "$HEALTH_URL" > /dev/null 2>&1; then
        echo "健康检查通过。"
        break
    fi
    if [ "$i" -eq "$MAX_RETRIES" ]; then
        echo "健康检查失败（已重试 $MAX_RETRIES 次）。"
        echo "查看日志： $DC logs backend"
        exit 1
    fi
    sleep 2
done

echo ""
echo "===== 部署完成 ====="
