"""Upstream configuration and durable namespace ownership (no remote calls)."""
import json
from urllib.parse import urlsplit


def validate_upstreams(items):
    if not isinstance(items, list):
        raise ValueError('UPSTREAMS 必须是数组')
    result, ids, names = [], set(), set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError('上游配置必须是对象')
        values = {key: item.get(key) for key in ('id', 'name', 'url', 'label_ids')}
        if any(not isinstance(value, str) or not value.strip() for value in values.values()):
            raise ValueError('上游 ID、名称、地址和标签不能为空且必须为字符串')
        values = {key: value.strip() for key, value in values.items()}
        values['name'] = values['name'].lower()
        if '.' in values['name'] or any(c.isspace() for c in values['name']):
            raise ValueError('上游名称不能包含点号或空白')
        if values['id'] in ids or values['name'] in names:
            raise ValueError('上游 ID 和名称必须唯一（名称不区分大小写）')
        url = urlsplit(values['url'])
        if url.scheme not in {'http', 'https'} or not url.netloc or url.query or url.fragment:
            raise ValueError('上游地址必须为不含查询参数和片段的 HTTP(S) 地址')
        labels = [s.strip() for s in values['label_ids'].split(',') if s.strip()]
        if not labels or not all(s.isdigit() for s in labels):
            raise ValueError('上游标签必须为逗号分隔的数字 ID')
        values['url'] = values['url'].rstrip('/')
        values['label_ids'] = ','.join(labels)
        ids.add(values['id'])
        names.add(values['name'])
        result.append(values)
    return result


def route_key(name, source_id):
    if not isinstance(source_id, (str, int)) or isinstance(source_id, bool) or not str(source_id).strip():
        raise ValueError('上游 Agent 缺少有效原始 ID')
    # Lowercase-safe, injective encoding: preserve ordinary numeric/string IDs,
    # escape uppercase, dots, whitespace, percent signs and non-ASCII bytes.
    encoded = ''.join(chr(b) if chr(b) in 'abcdefghijklmnopqrstuvwxyz0123456789_-'
                      else f'%{b:02x}' for b in str(source_id).encode('utf-8'))
    return f'{name}.{encoded}'


def bindings(repo):
    with repo.connect() as db:
        return {key[len('upstream_name:'):]: value for key, value in
                db.execute("SELECT key,value FROM metadata WHERE key LIKE 'upstream_name:%'")}


def validate_ownership(items, repo):
    owners = bindings(repo)
    for item in items:
        if item['id'] in owners and owners[item['id']] != item['name']:
            raise ValueError('已拉取上游的名称不可修改')
        if any(name == item['name'] and identity != item['id'] for identity, name in owners.items()):
            raise ValueError('该上游名称已被历史数据占用，不能重新分配')


def lock_name(db, upstream_id, name):
    key = f'upstream_name:{upstream_id}'
    existing = db.execute('SELECT value FROM metadata WHERE key=?', (key,)).fetchone()
    if existing and existing[0] != name:
        raise ValueError('已拉取上游的名称不可修改')
    other = db.execute("SELECT key FROM metadata WHERE key LIKE 'upstream_name:%' AND value=? AND key<>?",
                       (name, key)).fetchone()
    if other:
        raise ValueError('该上游名称已被历史数据占用')
    db.execute('INSERT OR IGNORE INTO metadata VALUES (?,?)', (key, name))


def migrate_default(repo):
    from intent_hub.config import Config
    from intent_hub.models import RouteConfig
    from intent_hub.services.route_service import RouteService

    default = next((s for s in Config.get_upstreams() if s['id'] == Config.SOURCE_INSTANCE), None)
    if default is None:
        return
    with repo.transaction() as db:
        if db.execute("SELECT 1 FROM metadata WHERE key='upstream_identity_v2'").fetchone():
            return
        routes = [RouteConfig.model_validate_json(row[0]) for row in db.execute('SELECT body FROM entities')]
        legacy = [r for r in routes if r.source and r.source.type == 'upstream_agent'
                  and r.source.instance == Config.SOURCE_INSTANCE]
        if not legacy:
            return
        targets = {r.id: route_key(default['name'], r.source.source_id) for r in legacy}
        keys = [targets.get(r.id, r.route_key) for r in routes]
        if len(keys) != len(set(keys)):
            raise ValueError('默认上游迁移存在路由标识或原始 ID 冲突，未修改数据')
        # Two-phase rename also handles a legacy key that is another row's target.
        for r in legacy:
            db.execute('UPDATE entities SET route_key=? WHERE id=?', (f'__migration__.{r.id}', r.id))
        for r in legacy:
            previous = r.model_copy(deep=True)
            r.route_key = targets[r.id]
            if r.route_key != previous.route_key:
                RouteService._mark_changed(r, previous=previous)
            repo.save(r, db, enqueue=r.route_key != previous.route_key)
        lock_name(db, default['id'], default['name'])
        db.execute("INSERT INTO metadata VALUES ('upstream_identity_v2','1')")


def settings_view(repo):
    from intent_hub.config import Config
    owners = bindings(repo)
    result = []
    for item in Config.get_upstreams():
        state = repo.metadata(f"upstream_pull:{item['id']}")
        result.append({**item, 'name_locked': item['id'] in owners,
                       'last_result': json.loads(state) if state else None})
    return {**Config.to_dict(), 'UPSTREAMS': result}
