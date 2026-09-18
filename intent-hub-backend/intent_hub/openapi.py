"""Generate/check the HTTP route inventory and shared request/response schemas."""
import argparse
import json
import re
from pathlib import Path

from intent_hub.app import app
from intent_hub import models, compat_models


def document():
    paths = {}
    for rule in app.url_map.iter_rules():
        if rule.endpoint == 'static':
            continue
        path = re.sub(r'<(?:[^:>]+:)?([^>]+)>', r'{\1}', rule.rule)
        bupt = rule.endpoint.startswith('bupt.') or rule.endpoint.startswith('bupt_root_')
        for method in sorted(rule.methods - {'HEAD', 'OPTIONS'}):
            operation = {'operationId': rule.endpoint.replace('.', '_') + '_' + method.lower(),
                'tags': ['bupt' if bupt else 'master'],
                'responses': {'200': {'description': 'Completed response; see API.md for endpoint-specific statuses and errors.'}},
                'security': [{'BearerAuth': []}]}
            if path.endswith('/health') or path.endswith('/auth/login'):
                operation['security'] = []
            if rule.arguments:
                operation['parameters'] = [{'name': name, 'in': 'path', 'required': True,
                    'schema': {'type': 'integer' if name != 'task_id' else 'string'}} for name in sorted(rule.arguments)]
            base = path.removeprefix('/compat/master').removeprefix('/compat/bupt')
            request_type = None
            if method == 'POST':
                request_type = {'/predict': 'PredictRequest', '/route': 'RouteRequest', '/auth/login': 'LoginRequest',
                                '/routes': 'RouteConfig', '/agents': 'AgentCreate', '/routes/merge': 'MergeAgentsRequest',
                                '/diagnostics/merge': 'MergeAgentsRequest'}.get(base)
            if method == 'PATCH' and base == '/agents/{agent_id}':
                request_type = 'AgentUpdate'
            if request_type:
                operation['requestBody'] = {'required': True, 'content': {'application/json': {'schema': {'$ref': '#/components/schemas/' + request_type}}}}
            if base == '/predict':
                operation['responses']['200']['content'] = {'application/json': {'schema': {'type': 'array', 'items': {'$ref': '#/components/schemas/PredictResponse'}}}}
            if base == '/route':
                operation['responses']['200']['description'] = 'BUPT success/data/error envelope; data.agents contains agent details and nullable score.'
            if base in {'/routes', '/agents', '/routes/merge', '/diagnostics/merge', '/collections', '/settings/qdrant-collections'} and method == 'POST':
                operation['responses'] = {'201': {'description': 'Created'}}
            if base == '/reindex':
                operation['responses']['202'] = {'description': 'Incremental task queued; full rebuild returns 200 on completion.'}
            paths.setdefault(path, {})[method.lower()] = operation
    schemas = {}
    for module, names in [(models, ['PredictRequest', 'PredictResponse', 'RouteConfig', 'LoginRequest']),
                          (compat_models, ['RouteRequest', 'Agent', 'AgentCreate', 'AgentUpdate', 'MergeAgentsRequest'])]:
        for name in names:
            schema = getattr(module, name).model_json_schema(ref_template='#/components/schemas/{model}')
            schemas.update(schema.pop('$defs', {}))
            schemas[name] = schema
    return {'openapi': '3.1.0', 'info': {'title': 'Unified Intent Hub', 'version': '0.2.0',
            'description': 'Generated route inventory for master profile. Fixed compatibility namespaces are stable; root aliases follow API_COMPAT_PROFILE.'},
            'paths': paths, 'components': {'schemas': schemas, 'securitySchemes': {'BearerAuth': {'type': 'http', 'scheme': 'bearer'}}}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default=str(Path(__file__).resolve().parents[2] / 'docs/intent-hub-openapi.json'))
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    path = Path(args.output)
    data = document()
    if args.check:
        if json.loads(path.read_text(encoding='utf-8')) != data:
            raise SystemExit('OpenAPI inventory is stale')
        print('OpenAPI inventory and schemas match registered routes')
    else:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(f'Wrote {len(data["paths"])} paths')


if __name__ == '__main__':
    main()
