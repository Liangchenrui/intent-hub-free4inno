#!/bin/sh
# 加载镜像内默认 .env（可被运行时环境变量覆盖）
# 若 .env 为 Windows 换行(CRLF)，先去除 \r 再 source，避免 ": not found" 与后续 HTTP 头非法字符
if [ -f /app/.env ]; then
  set -a
  # 用 tr 去掉 \r 后逐行 export，避免 source 把 \r 当命令执行
  _env_file="/tmp/.env.$$"
  tr -d '\r' < /app/.env > "$_env_file" && . "$_env_file"; rm -f "$_env_file"
  set +a
fi
# 启动时确保挂载卷归 appuser 所有（命名卷挂载后常为 root）
for dir in "$HF_HOME" /app/intent_hub/models; do
  [ -n "$dir" ] && [ -d "$dir" ] && chown -R appuser:appuser "$dir" 2>/dev/null || true
done
exec gosu appuser "$@"
