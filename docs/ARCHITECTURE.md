# Architecture

```text
Upstream Agent API -> AgentSource -> local SQLite AgentStore
                                  -> existing embedding service -> Qdrant

User query -> existing embedding service -> Qdrant corpus -> all threshold matches
                                                        -> optional definition Top-K + LLM
                                                        -> Agent details or default_route.txt
```

Qdrant keeps the established positive and negative payload fields. Full upstream Agent details live in SQLite. Each active Agent additionally has one `is_route_metadata=true` point encoding `title` and `text`, with `description_hash` and `route_hash` to reject stale candidates. Corpus matching, diagnostics and corpus restoration exclude those points.

Incremental sync includes description text, embedding model and index format version in the Agent hash to backfill older collections. Matching description vectors are reused before route replacement; missing metadata triggers backfill even when the saved Agent hash is unchanged. Index counts include description points, including Agents without utterances. SQLite sync hashes advance only after successful vector writes and validation; concurrent Agent edits remain detectable by current hashes.

Fallback preserves negative exclusions and active status, validates structured decisions and reloads the selected Agent before returning current details. Each invocation owns an `httpx.AsyncClient` and event loop with a model deadline and no retries; it does not share closed-loop connections or introduce LangChain. OpenAI-compatible providers and Gemini use existing non-secret settings and the environment-only LLM key. See [the branch delivery record](changes/llm-fallback/README.md).

