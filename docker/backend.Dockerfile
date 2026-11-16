# compsphere-server 镜像
# build context = 仓库根目录（docker-compose 已如此配置）
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# WeasyPrint 渲染证书 PDF 所需系统库 + 中文字体（证书版式含中文）
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 \
        fonts-noto-cjk curl git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 依赖层独立缓存；backend/requirements 就绪前此行会失败 —— 属预期（目录现为占位）
COPY backend/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY backend/ ./
RUN adduser --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/healthz/ || exit 1
