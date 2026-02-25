"""
OpenAPI / Swagger auto-documentation for SpokedPy.

Generates an OpenAPI 3.0 specification dynamically from the Flask
app's url_map and view-function docstrings.  Serves Swagger UI from
unpkg CDN — zero extra Python dependencies.

Usage:
    from web_interface.swagger import register_swagger
    register_swagger(app)

Provides:
    GET  /api/docs        → Swagger UI (HTML page)
    GET  /api/docs/spec   → OpenAPI 3.0 JSON spec
"""

import os
import re
from flask import Blueprint, jsonify, request

swagger_bp = Blueprint('swagger', __name__)

# ─────────────────────────────────────────────────────────────────────
# OpenAPI spec builder
# ─────────────────────────────────────────────────────────────────────

# HTTP methods we document (skip HEAD / OPTIONS)
_DOC_METHODS = {'GET', 'POST', 'PUT', 'PATCH', 'DELETE'}

# Map Flask converters to OpenAPI types
_CONVERTER_MAP = {
    'string': ('string', None),
    'int':    ('integer', 'int32'),
    'float':  ('number', 'double'),
    'path':   ('string', None),
    'uuid':   ('string', 'uuid'),
}

# Pattern to pull path params from Flask rule strings
_PARAM_RE = re.compile(r'<(?:(\w+):)?(\w+)>')

# Logical groupings by URL prefix
_TAG_MAP = [
    ('/api/hub',                  'Settings Hub'),
    ('/api/engines',              'Engines'),
    ('/api/marshal',              'Marshal Tokens'),
    ('/api/staging',              'Staging Pipeline'),
    ('/api/registry',             'Node Registry'),
    ('/api/execution',            'Execution'),
    ('/api/settings',             'Settings'),
    ('/api/projects',             'Projects'),
    ('/api/canvas',               'Canvas'),
    ('/api/paradigms',            'Paradigms'),
    ('/api/uir',                  'UIR'),
    ('/api/session',              'Session Ledger'),
    ('/api/runtime',              'Runtime'),
    ('/api/ai',                   'AI Chat'),
    ('/api/ast-grep',             'AST-Grep'),
    ('/api/library',              'Library'),
    ('/api/export',               'Export'),
    ('/api/repository',           'Repository'),
    ('/api/demos',                'Demos'),
]


def _tag_for_rule(rule: str) -> str:
    """Derive a Swagger tag from the URL path."""
    for prefix, tag in _TAG_MAP:
        if rule.startswith(prefix):
            return tag
    return 'Other'


def _parse_path_params(rule_str: str):
    """Convert Flask '<type:name>' placeholders to OpenAPI path params."""
    params = []
    for match in _PARAM_RE.finditer(rule_str):
        converter = match.group(1) or 'string'
        name = match.group(2)
        schema_type, schema_fmt = _CONVERTER_MAP.get(converter, ('string', None))
        p = {
            'name': name,
            'in': 'path',
            'required': True,
            'schema': {'type': schema_type},
        }
        if schema_fmt:
            p['schema']['format'] = schema_fmt
        params.append(p)
    return params


def _flask_to_openapi_path(rule_str: str) -> str:
    """Convert '/api/staging/snippet/<staging_id>' → '/api/staging/snippet/{staging_id}'."""
    return _PARAM_RE.sub(lambda m: '{' + m.group(2) + '}', rule_str)


def _build_operation(rule, method, view_func):
    """Build one OpenAPI operation object from a Flask route."""
    docstring = (view_func.__doc__ or '').strip()
    summary_line = docstring.split('\n')[0] if docstring else f'{method} {rule.rule}'
    description = docstring if docstring else None

    op = {
        'summary': summary_line,
        'tags': [_tag_for_rule(rule.rule)],
        'responses': {
            '200': {'description': 'Successful response'},
        },
    }
    if description:
        op['description'] = description

    # Path parameters
    params = _parse_path_params(rule.rule)

    # Query parameters — sniff from docstring for common ones
    if method == 'GET':
        if 'limit' in docstring.lower():
            params.append({
                'name': 'limit', 'in': 'query', 'required': False,
                'schema': {'type': 'integer', 'default': 50},
            })
        if 'include_history' in docstring.lower() or 'include_history' in rule.rule:
            params.append({
                'name': 'include_history', 'in': 'query', 'required': False,
                'schema': {'type': 'integer', 'enum': [0, 1], 'default': 0},
            })
        if 'last_n' in docstring.lower():
            params.append({
                'name': 'last_n', 'in': 'query', 'required': False,
                'schema': {'type': 'integer', 'default': 10},
            })

    if params:
        op['parameters'] = params

    # Request body for write methods
    if method in ('POST', 'PUT', 'PATCH'):
        op['requestBody'] = {
            'required': True,
            'content': {
                'application/json': {
                    'schema': {'type': 'object'},
                },
            },
        }

    return op


def build_openapi_spec(app) -> dict:
    """Build the complete OpenAPI 3.0 specification from the Flask app."""
    # Resolve host/port dynamically
    host = os.environ.get('SPOKEDPY_HOST', '0.0.0.0')
    port = os.environ.get('SPOKEDPY_PORT', '5002')
    display_host = 'localhost' if host in ('0.0.0.0', '::') else host

    spec = {
        'openapi': '3.0.3',
        'info': {
            'title': 'SpokedPy API',
            'description': (
                'REST API for SpokedPy — a polyglot visual programming platform '
                'with 15 language engines, a 4-phase staging pipeline, '
                'marshal token gateway, node registry matrix, and live execution.'
            ),
            'version': '1.0.0',
            'contact': {
                'name': 'SpokedPy',
            },
        },
        'servers': [
            {
                'url': f'http://{display_host}:{port}',
                'description': 'Local development server',
            },
        ],
        'tags': [
            {'name': tag, 'description': f'{tag} endpoints'}
            for _, tag in _TAG_MAP
        ],
        'paths': {},
    }

    # Collect all /api/* routes
    for rule in app.url_map.iter_rules():
        if not rule.rule.startswith('/api/'):
            continue
        if rule.rule in ('/api/docs', '/api/docs/spec'):
            continue  # don't document the docs routes themselves

        view_func = app.view_functions.get(rule.endpoint)
        if view_func is None:
            continue

        openapi_path = _flask_to_openapi_path(rule.rule)
        if openapi_path not in spec['paths']:
            spec['paths'][openapi_path] = {}

        for method in sorted(rule.methods & _DOC_METHODS):
            method_lower = method.lower()
            if method_lower not in spec['paths'][openapi_path]:
                spec['paths'][openapi_path][method_lower] = _build_operation(
                    rule, method, view_func
                )

    return spec


# ─────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────

@swagger_bp.route('/api/docs/spec', methods=['GET'])
def openapi_spec():
    """Return the OpenAPI 3.0 specification as JSON."""
    from flask import current_app
    spec = build_openapi_spec(current_app)
    return jsonify(spec)


@swagger_bp.route('/api/docs', methods=['GET'])
def swagger_ui():
    """Serve the Swagger UI page.

    Uses Swagger UI from unpkg CDN — no local files needed.
    The spec URL resolves dynamically to the current host:port.
    """
    # Build spec URL relative to the current request so it works
    # regardless of what host/port the user accesses from.
    spec_url = f'{request.scheme}://{request.host}/api/docs/spec'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SpokedPy API Documentation</title>
    <link rel="stylesheet" href="./swagger-ui.css">
    <style>
        html {{ box-sizing: border-box; overflow-y: scroll; }}
        *, *::before, *::after {{ box-sizing: inherit; }}
        body {{ margin: 0; background: #fafafa; }}
        .swagger-ui .topbar {{ display: none; }}
        /* When loaded inside an iframe, remove excess padding */
        .swagger-ui .wrapper {{ padding: 0 10px; }}
        .swagger-ui .info {{ margin: 12px 0; }}
        .swagger-ui .scheme-container {{ padding: 10px 0; }}
    </style>
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
        SwaggerUIBundle({{
            url: "{spec_url}",
            dom_id: '#swagger-ui',
            deepLinking: true,
            presets: [
                SwaggerUIBundle.presets.apis,
                SwaggerUIBundle.SwaggerUIStandalonePreset
            ],
            layout: "BaseLayout",
            defaultModelsExpandDepth: -1,
            docExpansion: "list",
            filter: true,
            tryItOutEnabled: true,
        }});
    </script>
</body>
</html>"""
    return html, 200, {'Content-Type': 'text/html; charset=utf-8'}


# ─────────────────────────────────────────────────────────────────────
# Registration helper
# ─────────────────────────────────────────────────────────────────────

def register_swagger(app):
    """Register the Swagger blueprint with the Flask app.

    Call this AFTER all other blueprints have been registered so the
    spec generator can see every route.
    """
    app.register_blueprint(swagger_bp)
    print(f"  Swagger UI:    /api/docs")
    print(f"  OpenAPI spec:  /api/docs/spec")
