# Docs

当前项目公共文档统一维护在根目录 `docs/`。

- `API.md`：后端接口与鉴权说明
- `ARCHITECTURE.md`：代码结构、运行时数据布局、兼容层说明
- `intent-hub-openapi.json`：可导入 Apifox 等工具的 OpenAPI 文档
- `bupt-routing-api.openapi.yaml`：BUPT 契约对外路由接口（`POST /compat/bupt/route`、`POST /route`）的 OpenAPI 3.1 契约，含鉴权方式、字段语义、错误与示例
- `superpowers/`：过程性设计与计划文档
- [大模型兜底需求与交付记录](changes/llm-fallback/README.md)：需求、设计取舍、实现入口、验收证据、本地运行与待验证项
- [master 与 BUPT 统一方案](changes/branch-unification/README.md)：需求、实现与兼容契约、迁移工具、验证证据及交付状态
- [运行日志与路由记录](changes/logging/README.md)：已确定需求、建议设计及逐步实现状态
- [路由时延优化](changes/routing-latency/README.md)：组件预热、客户端复用、并行检索与真实对照证据
- [低时延增量同步修复](changes/incremental-sync/README.md)：实际变更检测、例句向量复用、失败恢复和验收

历史说明中的 `python -m scripts.api_docs check` 和 `update-api-md` 在当前仓库缺少对应模块，暂不可执行。统一版本改用后端目录下的 `python -m intent_hub.openapi --check`，并结合 `API.md` 和相关后端测试核对。

子项目仅在需要独立说明时保留局部文档。

- [历史冲突演示](DEMO_CONFLICT_REPAIR.md)与[中英文讲稿](DEMO_ORAL_SCRIPT_BILINGUAL.md)：保留自 BUPT 的演示背景，不作为统一版本实测结论。

- [上游快速拉取与差量同步](changes/upstream-pull/README.md)：并发抓取、差量保存、后台任务与验收。
