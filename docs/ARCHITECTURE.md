# Architecture

```text
Upstream Agent API -> AgentSource -> local agents.json snapshot
                                  -> existing embedding service -> Qdrant

User query -> existing embedding service -> Qdrant -> snapshot detail or default_route.txt
```

Qdrant keeps the established positive and negative payload fields. Full upstream Agent details live in the local snapshot so vector payloads do not change.

