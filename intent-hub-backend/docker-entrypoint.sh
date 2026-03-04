#!/bin/sh
# 启动时确保挂载卷归 appuser 所有（命名卷挂载后常为 root）
for dir in "$HF_HOME" /app/intent_hub/models; do
  [ -n "$dir" ] && [ -d "$dir" ] && chown -R appuser:appuser "$dir" 2>/dev/null || true
done
exec gosu appuser "$@"
