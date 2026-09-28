"""Persist successful fallback examples without delaying for vector synchronization."""
from datetime import datetime, timezone

from intent_hub.models import RouteConfig
from intent_hub.services.route_service import RouteService
from intent_hub.services.sync_task_service import get_sync_task_service
from intent_hub.utils.logger import logger
from intent_hub.utils.route_trace import trace_event


def learn_fallback(manager, selected: RouteConfig, text: str) -> None:
    text = text.strip()
    if not text:
        return
    try:
        repo = manager.route_manager.repository
        with repo.transaction() as db:
            row = db.execute('SELECT body FROM entities WHERE id=?', (selected.id,)).fetchone()
            if not row:
                return
            current = RouteConfig.model_validate_json(row[0])
            if current.lifecycle_status != 'active':
                return
            if text in {sample.strip() for sample in current.utterances}:
                trace_event('fallback_learning', route_id=current.id, status='duplicate')
                return
            # Never learn against a capability changed since the model decision.
            if manager.route_manager.compute_route_hash(current) != manager.route_manager.compute_route_hash(selected):
                trace_event('fallback_learning', route_id=current.id, status='changed')
                return
            updated = current.model_copy(deep=True)
            updated.utterances.append(text)
            updated.fallback_utterances[text] = datetime.now(timezone.utc).isoformat()
            RouteService._mark_changed(updated, previous=current,
                manual_overrides=current.sync.manual_overrides if current.sync else [])
            repo.save(updated, db)
        trace_event('fallback_learning', route_id=selected.id, status='saved')
    except Exception as exc:
        trace_event('fallback_learning', route_id=selected.id, status='failed', error_type=type(exc).__name__)
        logger.warning('Fallback sample persistence failed route_id=%s (%s)', selected.id, type(exc).__name__)
        return
    try:
        get_sync_task_service(getattr(manager, 'owner', manager)).enqueue_routes([selected.id])
    except Exception as exc:
        # The transactional outbox remains recoverable on queue restart.
        trace_event('fallback_learning', route_id=selected.id, status='sync_pending', error_type=type(exc).__name__)
        logger.warning('Fallback sample sync pending route_id=%s (%s)', selected.id, type(exc).__name__)
