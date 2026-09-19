"""Business categories shared by HTTP requests and background workers."""

from contextlib import contextmanager
from contextvars import ContextVar

CATEGORIES = {"routing", "sync", "diagnostics", "management", "system"}
log_category = ContextVar("log_category", default=None)


@contextmanager
def log_scope(category):
    token = log_category.set(category)
    try:
        yield
    finally:
        log_category.reset(token)


def classify_log(kind="runtime", path="", source="", message=""):
    """Legacy fallback is best effort; newly collected logs persist their category."""
    path = path.removeprefix("/compat/master").removeprefix("/compat/bupt")
    if kind == "routing" or path in {"/predict", "/route"}:
        return "routing"
    if any(part in path for part in ("/sync", "/reindex", "/pull", "/upstream-pull")):
        return "sync"
    if path.startswith("/diagnostics"):
        return "diagnostics"
    if any(name in source for name in ("sync_service", "sync_task_service", "delta_sync", "agent_source")):
        return "sync"
    if "diagnostic" in source:
        return "diagnostics"
    if message.startswith(("Route sync ", "Sync task ", "Starting sync", "Sync completed")):
        return "sync"
    if message.startswith(("LLM fallback ", "Creating LLM instance:", "Matched route count:", "Negative excluded:")):
        # LLM factory also serves management actions; an HTTP path takes precedence.
        if not path:
            return "routing"
    if path.startswith(("/agents", "/routes", "/settings", "/auth", "/collections")):
        return "management"
    return "system"
