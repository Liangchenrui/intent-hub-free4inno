# 页面配置统一路由 API 密钥

2026-09-28：修复 Settings 的 Route API Key 只写浏览器、未设置后端且不适用于 `/route` 的问题。

## 行为

- 页面绑定 `ROUTE_API_KEY`，通过管理员鉴权的 `/compat/master/settings` 保存至本地 `settings.json`，保存成功立即生效，重启保留。
- 非空统一密钥优先于 `PREDICT_AUTH_KEY` 和 `AUTH_CODE`，用于 `/predict`、`/route` 及对应固定兼容路径。轮换后旧路由密钥不再通过；master 仍允许已登录的管理员令牌进行测试。
- 留空恢复原来的环境变量鉴权规则，不更改 `AUTH_ENABLED`。BUPT 无有效密钥时仍拒绝访问。
- 统一密钥只用于路由，不授予管理权限；BUPT 管理接口继续使用原 `AUTH_CODE`。管理员登录密码保持现状。
- 管理设置接口可读回统一密钥（与现有 LLM key 设置模式一致），浏览器以密码输入框显示，并用于测试请求。运行日志对统一密钥脱敏。
- 输入必须为字符串，移除首尾空白，不允许内部空白；无效输入不修改文件和当前配置。

## 验证与交付

回归覆盖实际 HTTP 登录、管理员保存、四个路由路径、错误密钥拒绝、密钥轮换、配置重新加载、清空回退、管理权限隔离与无效值原子性。使用临时配置，不改用户的现有密钥。

Windows 本地验证（2026-09-28，根目录 `PYTHONPATH=intent-hub-backend`）：

- `python -m pytest intent-hub-backend/tests/test_config.py intent-hub-backend/tests/test_settings_api.py intent-hub-backend/tests/test_unification.py -q`：与新增用例同批执行，原有 40 项通过。
- 新用例首次失败来自测试写死旧登录密码及空对象触发现有输入校验问题。改为使用当前配置登录，使用非空的无效业务输入检验鉴权（避免调用真实模型）；`python -m pytest intent-hub-backend/tests/test_route_api_key.py -q`：2 passed，26.48s。鉴权成功返回业务参数错误，错误密钥返回 401。
- `npm run build`：通过（既有大 bundle 提示）；`git diff --check` 通过。
- 本地后端重启后，前端代理 `/api/health/ready` 返回 200 / ready。浏览器验证登录成功；未通过浏览器保存真实密钥。未远程部署。

本次只修复配置能力，不替用户选择或保存新的真实密钥。单进程本地服务保存后立即生效；多进程部署应在保存后重启所有 worker 统一加载文件，尚未实现跨进程热更新。
