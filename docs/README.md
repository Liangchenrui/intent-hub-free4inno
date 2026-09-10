# Docs

当前项目公共文档统一维护在根目录 `docs/`。

- `API.md`：后端接口与鉴权说明
- `ARCHITECTURE.md`：代码结构、运行时数据布局、兼容层说明
- `intent-hub-openapi.json`：可导入 Apifox 等工具的 OpenAPI 文档
- `superpowers/`：过程性设计与计划文档
- [大模型兜底需求与交付记录](changes/llm-fallback/README.md)：需求、设计取舍、实现入口、验收证据、本地运行与待验证项

历史说明中的 `python -m scripts.api_docs check` 和 `update-api-md` 在当前仓库缺少对应模块，暂不可执行。接口契约先结合 `API.md`、Flask 路由实现和相关后端测试核对，不将缺失工具的检查标记为通过。

子项目仅在需要独立说明时保留局部文档。
