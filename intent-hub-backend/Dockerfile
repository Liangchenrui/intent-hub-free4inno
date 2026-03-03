ARG BASE_IMAGE=swr.cn-north-4.myhuaweicloud.com/ddn-k8s/ghcr.io/astral-sh/uv:python3.11-bookworm-slim
FROM ${BASE_IMAGE} AS builder

ARG PIP_INDEX_URL

WORKDIR /build

ENV UV_HTTP_TIMEOUT=600 \
    UV_LINK_MODE=copy \
    UV_CONCURRENT_DOWNLOADS=1

# 创建虚拟环境
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .

# 使用 uv 加速安装
RUN --mount=type=cache,target=/root/.cache/uv \
    if [ -n "$PIP_INDEX_URL" ]; then \
    uv pip install --index-strategy unsafe-best-match -i $PIP_INDEX_URL --extra-index-url https://mirrors.aliyun.com/pytorch-wheels/cpu -r requirements.txt; \
    else \
    uv pip install --index-strategy unsafe-best-match --extra-index-url https://mirrors.aliyun.com/pytorch-wheels/cpu -r requirements.txt; \
    fi

# 构建阶段完成，直接进入最终镜像构建
# 移除了本地模型下载步骤，因为已改用外部 Embedding 服务

FROM ${BASE_IMAGE}

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:${PATH}"

# 安装 gosu，供 entrypoint 切换用户
RUN apt-get update && apt-get install -y --no-install-recommends gosu && \
    rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# 复制虚拟环境
COPY --from=builder --chown=appuser:appuser /opt/venv /opt/venv

COPY --chown=appuser:appuser . .

# 创建必要的目录
RUN mkdir -p /app/intent_hub/models /app/data && \
    chown -R appuser:appuser /app/intent_hub/models /app/data

COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 5000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["python", "run.py"]
