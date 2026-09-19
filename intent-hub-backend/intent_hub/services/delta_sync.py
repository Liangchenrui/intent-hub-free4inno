"""Idempotent per-route vector deltas; metadata is the final commit record."""
from datetime import datetime, timezone
from time import perf_counter
import uuid

from qdrant_client.models import PointStruct

from intent_hub.config import Config
from intent_hub.intent_description import description_hash, description_text
from intent_hub.models import RouteConfig


SYNC_SCHEMA = 1


def business_snapshot(route):
    body = route.model_dump(exclude={'sync', 'updated_at', 'source', 'details'})
    body['utterances'] = sorted(set(route.utterances))
    body['negative_samples'] = sorted(set(route.negative_samples))
    return body


def sync_delta(service, route, metadata=None):
    started = perf_counter()
    manager = service.component_manager
    q = manager.qdrant_client
    route_hash = manager.route_manager.compute_route_hash(route)
    model = Config.EMBEDDING_MODEL_NAME
    desc_hash = description_hash(route, model)
    if metadata is None:
        metadata = q.get_route_metadata([route.id]).get(route.id, {})
    old = metadata.get('route_config')
    previous = RouteConfig.model_validate(old) if old else None
    committed = metadata.get('sync_schema') == SYNC_SCHEMA
    same = (committed and metadata.get('route_hash') == route_hash
            and metadata.get('description_hash') == desc_hash and previous is not None
            and business_snapshot(previous) == business_snapshot(route))
    result = {'route_id': route.id, 'route_name': route.name, 'total_points': 0,
              'total_negative_points': 0, 'encoded_texts': 0, 'changed': not same,
              'metadata_committed': True, 'timings_ms': {}}
    if same:
        if not route.sync or route.sync.status != 'synced' or route.sync.synced_version != route.sync.version:
            service._mark_synced_if_current(route.id, route.sync.version if route.sync else 0)
        result['timings_ms']['total'] = round((perf_counter() - started) * 1000, 3)
        return result

    # Read only this route when a business delta or legacy upgrade is necessary.
    points = q.get_route_points(route.id)
    existing = {}
    reusable = {}
    for point in points:
        payload = point.payload or {}
        if payload.get('is_route_metadata'):
            continue
        text = payload.get('utterance')
        kind = bool(payload.get('is_negative'))
        existing.setdefault((kind, text), []).append(point)
        point_model = payload.get('model_name')
        # Legacy negatives lack a model; only trust the last committed metadata.
        if point_model is None and metadata.get('route_hash') and metadata.get('model_name') == model:
            point_model = model
        if (point_model == model and isinstance(point.vector, list)
                and len(point.vector) == q.dimensions and any(point.vector)):
            reusable[text] = point.vector

    desired = [(False, text) for text in dict.fromkeys(route.utterances)]
    desired += [(True, text) for text in dict.fromkeys(route.negative_samples)]
    missing = list(dict.fromkeys(text for _, text in desired if text not in reusable))
    description_vector = None
    description_valid = False
    if metadata.get('description_hash') == desc_hash:
        description_point = next((p for p in points if (p.payload or {}).get('is_route_metadata')), None)
        if description_point is not None:
            vector = description_point.vector
            description_valid = isinstance(vector, list) and len(vector) == q.dimensions and any(vector)
    desc_text = description_text(route)
    if not description_valid and desc_text not in missing and desc_text not in reusable:
        missing.append(desc_text)
    result['timings_ms']['read_plan'] = round((perf_counter() - started) * 1000, 3)
    embedding_started = perf_counter()
    if missing:
        vectors = manager.encoder.encode(missing)
        if len(vectors) != len(missing):
            raise ValueError('Embedding count does not match sync plan')
        for text, vector in zip(missing, vectors):
            if len(vector) != q.dimensions or not any(vector):
                raise ValueError('Invalid embedding in sync plan')
            reusable[text] = vector
    result['encoded_texts'] = len(missing)
    result['timings_ms']['embedding'] = round((perf_counter() - embedding_started) * 1000, 3)
    if not description_valid:
        description_vector = reusable[desc_text]

    writes = []
    patches = {False: [], True: []}
    keep = set()
    common = {'route_id': route.id, 'route_name': route.name,
              'model_name': model}
    payloads = {
        False: {**common, 'score_threshold': route.score_threshold},
        True: {**common, 'is_negative': True, 'negative_threshold': route.negative_threshold},
    }
    for kind, text in desired:
        candidates = existing.get((kind, text), [])
        current = candidates[0] if candidates else None
        point_id = current.id if current else str(uuid.uuid5(uuid.NAMESPACE_DNS, f'sample-v2:{route.id}:{kind}:{text}'))
        keep.add(point_id)
        payload = {**payloads[kind], 'utterance': text}
        current_payload = current.payload if current else {}
        vector_valid = (current is not None and current_payload.get('model_name', metadata.get('model_name')) == model
                        and isinstance(current.vector, list) and len(current.vector) == q.dimensions and any(current.vector))
        if not vector_valid:
            writes.append(PointStruct(id=point_id, vector=reusable[text], payload=payload))
        elif any(current_payload.get(k) != v for k, v in payload.items()):
            patches[kind].append(point_id)
    removed = [p.id for group in existing.values() for p in group if p.id not in keep]

    write_started = perf_counter()
    # Invalidate before *any* partial mutation. Retry must inspect actual points,
    # even when an intervening edit reverted to the old business hash.
    metadata_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f'route-metadata:{route.id}'))
    if metadata:
        q.patch_points([metadata_id], {'sync_schema': 0})
    q._upsert_points(writes)
    for kind, ids in patches.items():
        q.patch_points(ids, payloads[kind])
    q.delete_points(removed)

    snapshot = route.model_copy(deep=True)
    snapshot.sync = snapshot.sync or RouteConfig.RouteSync()
    snapshot.sync.status = 'synced'
    snapshot.sync.synced_version = snapshot.sync.version
    snapshot.sync.last_synced_at = datetime.now(timezone.utc).isoformat()
    snapshot.sync.error = None
    if description_vector is not None:
        q.upsert_route_metadata(snapshot, route_hash=route_hash, model_name=model,
                                embedding=description_vector, sample_count=len(desired))
    else:
        # The final write certifies samples and metadata together.
        q.patch_points([metadata_id], {**common, 'route_hash': route_hash, 'route_config': snapshot.model_dump(),
                                     'sync_schema': SYNC_SCHEMA, 'sample_count': len(desired)})
    service._mark_synced_if_current(route.id, snapshot.sync.version)
    result['total_points'] = sum(not kind for kind, _ in desired)
    result['total_negative_points'] = sum(kind for kind, _ in desired)
    result['timings_ms']['write'] = round((perf_counter() - write_started) * 1000, 3)
    result['timings_ms']['total'] = round((perf_counter() - started) * 1000, 3)
    return result
