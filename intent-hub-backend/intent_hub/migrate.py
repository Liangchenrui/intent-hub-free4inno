"""Offline migration. Default dry-run; source files are never modified."""
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

from intent_hub.models import RouteConfig
from intent_hub.repository import Repository


FIELD_MAP = {'title': 'name', 'text': 'description'}


def read_source(path, contract, source):
    path = Path(path)
    if contract == 'master':
        raw = json.loads(path.read_text(encoding='utf-8'))
    else:
        with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True) as db:
            db.row_factory = sqlite3.Row
            raw = [dict(row) for row in db.execute('SELECT * FROM agents ORDER BY id')]
        for item in raw:
            for key in ('utterances', 'negative_samples', 'details', 'manual_overrides', 'source_snapshot'):
                item[key] = json.loads(item.get(key) or ('[]' if key in ('utterances', 'negative_samples', 'manual_overrides') else '{}'))
    routes = []
    for item in raw:
        if contract == 'master':
            route = RouteConfig(**item)
        else:
            upstream = item.get('source_type') == 'upstream'
            snapshot = {FIELD_MAP.get(k, k): v for k, v in item.get('source_snapshot', {}).items()}
            route = RouteConfig(
                id=item['id'], name=item['title'], description=item.get('text', ''),
                route_key=f"bupt.{source}.{item['id']}",
                utterances=item['utterances'], negative_samples=item['negative_samples'],
                score_threshold=item['score_threshold'], negative_threshold=item['negative_threshold'],
                details=item.get('details', {}), updated_at=item.get('updated_at'),
                lifecycle_status={'inactive': 'disabled'}.get(item['lifecycle_status'], item['lifecycle_status']),
                source=RouteConfig.RouteSource(type='upstream_agent' if upstream else 'web_manual',
                    instance=source, source_id=str(item.get('upstream_id') if item.get('upstream_id') is not None else item['id']) if upstream else None,
                    upstream_present=item.get('upstream_present'), source_snapshot=snapshot,
                    managed_fields=list(snapshot)),
                sync=RouteConfig.RouteSync(status='pending', version=1,
                    manual_overrides=[FIELD_MAP.get(k, k) for k in item.get('manual_overrides', [])]),
            )
        routes.append(route)
    if len({r.id for r in routes}) != len(routes) or len({r.route_key for r in routes}) != len(routes):
        raise ValueError('Duplicate source ID or route_key; migration aborted')
    return routes


def migrate(path, target, contract='master', source='default', apply=False):
    if not source or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in source):
        raise ValueError('source must be a stable alphanumeric identifier')
    if Path(path).resolve() == Path(target).resolve():
        raise ValueError('Target must differ from source')
    routes = read_source(path, contract, source)
    fingerprint = hashlib.sha256(json.dumps([r.model_dump() for r in routes], sort_keys=True).encode()).hexdigest()
    result = {'mode': 'apply' if apply else 'dry-run', 'contract': contract, 'source': source,
              'entities': len(routes), 'fingerprint': fingerprint, 'requires_reindex': True}
    if Path(target).exists():
        with sqlite3.connect(Path(target).resolve().as_uri() + '?mode=ro', uri=True) as db:
            try:
                prior = db.execute('SELECT value FROM metadata WHERE key=?', (f'migration:{contract}:{source}',)).fetchone()
                keys = {row[0] for row in db.execute('SELECT route_key FROM entities')}
                ids = {row[0] for row in db.execute('SELECT id FROM entities')}
            except sqlite3.DatabaseError as error:
                raise ValueError('Target is not a unified repository') from error
        if prior:
            if prior[0] != fingerprint:
                raise ValueError('Source changed after migration; use a fresh target or reconcile explicitly')
            result['already_applied'] = True
            return result
        if keys.intersection(r.route_key for r in routes):
            raise ValueError('Target route_key conflict; migration aborted')
        if contract == 'master' and ids.intersection(r.id for r in routes):
            raise ValueError('Master ID collision; migrate master first or use separate target databases')
    if not apply:
        return result
    repo = Repository(target)
    key = f'migration:{contract}:{source}'
    with repo.transaction() as db:
        old = db.execute('SELECT value FROM metadata WHERE key=?', (key,)).fetchone()
        if old:
            if old[0] != fingerprint:
                raise ValueError('Source changed after migration; use a fresh target or reconcile explicitly')
            result['already_applied'] = True
            return result
        used = {row[0] for row in db.execute('SELECT id FROM entities')}
        # Reserve all positive master IDs before allocating BUPT/internal IDs.
        if contract == 'master' and used.intersection(r.id for r in routes):
            raise ValueError('Master ID collision; use separate target databases')
        for route in routes:
            legacy = route.id
            if contract == 'bupt':
                route.id = repo.allocate(db)
            elif route.id <= 0:
                raise ValueError('Master IDs must be positive')
            repo.save(route, db)
            repo.bind(contract, source, legacy, route.id, db)
        db.execute('INSERT INTO metadata VALUES (?,?)', (key, fingerprint))
        db.execute("INSERT OR REPLACE INTO metadata VALUES ('legacy_imported','1')")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True)
    parser.add_argument('--target', required=True)
    parser.add_argument('--contract', choices=['master', 'bupt'], required=True)
    parser.add_argument('--source', default='default')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    print(json.dumps(migrate(args.input, args.target, args.contract, args.source, args.apply), ensure_ascii=False))


if __name__ == '__main__':
    main()
