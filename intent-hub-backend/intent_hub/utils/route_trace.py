"""Request-local routing evidence; no dependency on storage or routing services."""

from contextlib import contextmanager
from time import monotonic

from flask import g, has_request_context


def trace_event(stage, **fields):
    if has_request_context():
        if not hasattr(g, "route_events"):
            g.route_events = []
        now = monotonic()
        started = getattr(g, "log_started", now)
        g.route_events.append({"stage": stage, "offset_ms": round((now - started) * 1000, 3), **fields})


@contextmanager
def trace_stage(stage):
    """Measure executed work, including failures, without inferring time from events."""
    if not has_request_context():
        yield
        return
    started = monotonic()
    if not hasattr(g, "route_timings"):
        g.route_timings = []
    span = {"stage": stage,
            "offset_ms": round((started - getattr(g, "log_started", started)) * 1000, 3),
            "status": "succeeded"}
    g.route_timings.append(span)
    try:
        yield
    except BaseException as exc:
        span.update(status="failed", error_type=type(exc).__name__)
        raise
    finally:
        span["elapsed_ms"] = round((monotonic() - started) * 1000, 3)


def run_parallel_searches(negative, positive):
    """Wait for both workers before recording the request, including on failure."""
    from concurrent.futures import ThreadPoolExecutor
    from contextvars import copy_context

    if has_request_context():
        # Initialize shared per-request lists before either worker starts.
        if not hasattr(g, 'route_events'):
            g.route_events = []
        if not hasattr(g, 'route_timings'):
            g.route_timings = []

    def run(stage, operation):
        trace_event(stage)
        with trace_stage(stage):
            return operation()

    with ThreadPoolExecutor(max_workers=2, thread_name_prefix='route-search') as executor:
        neg = executor.submit(copy_context().run, run, 'negative_search', negative)
        pos = executor.submit(copy_context().run, run, 'positive_search', positive)
        return neg.result(), pos.result()


def remote_timing(service, elapsed_ms, server_ms=None):
    fields = {'service': service, 'elapsed_ms': round(elapsed_ms, 3)}
    if server_ms is not None:
        try:
            import math
            value = float(server_ms)
            if math.isfinite(value) and value >= 0:
                fields['server_ms'] = round(value, 3)
        except (TypeError, ValueError):
            pass
    trace_event('remote_call', **fields)
