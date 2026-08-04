# Docs

当前项目公共文档统一维护在根目录 `docs/`。

- `API.md`：后端接口与鉴权说明
- `ARCHITECTURE.md`：代码结构、运行时数据布局、兼容层说明
- `intent-hub-openapi.json`：可导入 Apifox 等工具的 OpenAPI 文档
- `superpowers/`：过程性设计与计划文档

API 路由清单由 Flask 路由表校验：

```bash
python -m scripts.api_docs check
python -m scripts.api_docs update-api-md
```

子项目仅在需要独立说明时保留局部文档。
