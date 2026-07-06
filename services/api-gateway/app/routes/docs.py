"""Unified API documentation that aggregates all microservice OpenAPI schemas."""
import logging
import time

import httpx
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# Cache for the merged schema (schema, timestamp)
_schema_cache: dict = {"schema": None, "ts": 0}
_CACHE_TTL_SECONDS = 300  # 5 minutes

SERVICE_SPECS = {
    "Auth": {"url": settings.AUTH_SERVICE_URL, "prefix": "/auth"},
    "Users": {"url": settings.USER_SERVICE_URL, "prefix": "/users"},
    "Rides": {"url": settings.RIDE_SERVICE_URL, "prefix": "/rides"},
    "Locations": {"url": settings.LOCATION_SERVICE_URL, "prefix": "/locations"},
    "Payments": {"url": settings.PAYMENT_SERVICE_URL, "prefix": "/payments"},
    "Tracking": {"url": settings.TRACKING_SERVICE_URL, "prefix": "/tracking"},
    "Notifications": {"url": settings.NOTIFICATION_SERVICE_URL, "prefix": "/notifications"},
}


async def _fetch_service_schema(
    client: httpx.AsyncClient, service_name: str, spec: dict
) -> dict | None:
    """Fetch OpenAPI schema from a single downstream service."""
    url = f"{spec['url']}{spec['prefix']}/openapi.json"
    try:
        resp = await client.get(url, timeout=5.0)
        if resp.status_code == 200:
            return resp.json()
        logger.warning(f"Failed to fetch schema from {service_name}: {resp.status_code}")
    except httpx.RequestError as e:
        logger.warning(f"Could not reach {service_name} for schema: {e}")
    return None


def _merge_schemas(service_schemas: dict[str, dict]) -> dict:
    """Merge multiple OpenAPI schemas into one unified schema."""
    merged = {
        "openapi": "3.1.0",
        "info": {
            "title": "MediRide API",
            "description": "Unified API documentation for all MediRide microservices.",
            "version": "1.0.0",
        },
        "paths": {},
        "components": {"schemas": {}, "securitySchemes": {}},
        "security": [{"BearerAuth": []}],
        "tags": [],
    }

    # Add BearerAuth security scheme
    merged["components"]["securitySchemes"]["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
    }

    for service_name, schema in service_schemas.items():
        if not schema:
            continue

        prefix = SERVICE_SPECS[service_name]["prefix"]

        # Add service-level tag
        merged["tags"].append({
            "name": service_name,
            "description": schema.get("info", {}).get("title", service_name),
        })

        # Merge paths — prefix them with /api/v1
        for path, path_item in schema.get("paths", {}).items():
            full_path = f"/api/v1{path}"
            # Tag each operation with the service name
            for method, operation in path_item.items():
                if isinstance(operation, dict):
                    existing_tags = operation.get("tags", [])
                    operation["tags"] = [service_name] + [
                        f"{service_name} > {t}" for t in existing_tags
                    ]
            merged["paths"][full_path] = path_item

        # Merge component schemas (prefix to avoid collisions)
        for comp_name, comp_schema in schema.get("components", {}).get("schemas", {}).items():
            key = f"{service_name}_{comp_name}" if comp_name in merged["components"]["schemas"] else comp_name
            # Fix $ref pointers if we renamed
            if key != comp_name:
                _rewrite_refs(path_item, comp_name, key)
            merged["components"]["schemas"][key] = comp_schema

    return merged


def _rewrite_refs(obj, old_name: str, new_name: str):
    """Recursively rewrite $ref pointers in a schema object."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "$ref" and isinstance(v, str) and v.endswith(f"/{old_name}"):
                obj[k] = v.replace(f"/{old_name}", f"/{new_name}")
            else:
                _rewrite_refs(v, old_name, new_name)
    elif isinstance(obj, list):
        for item in obj:
            _rewrite_refs(item, old_name, new_name)


async def _get_merged_schema() -> dict:
    """Get the merged schema, using cache if fresh."""
    now = time.time()
    if _schema_cache["schema"] and (now - _schema_cache["ts"]) < _CACHE_TTL_SECONDS:
        return _schema_cache["schema"]

    import asyncio

    service_schemas = {}
    async with httpx.AsyncClient() as client:
        tasks = {
            name: _fetch_service_schema(client, name, spec)
            for name, spec in SERVICE_SPECS.items()
        }
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for name, result in zip(tasks.keys(), results):
            if isinstance(result, Exception):
                logger.warning(f"Error fetching {name} schema: {result}")
                service_schemas[name] = None
            else:
                service_schemas[name] = result

    merged = _merge_schemas(service_schemas)
    _schema_cache["schema"] = merged
    _schema_cache["ts"] = now
    return merged


@router.get("/openapi.json", include_in_schema=False)
async def unified_openapi():
    """Combined OpenAPI schema from all microservices."""
    schema = await _get_merged_schema()
    return JSONResponse(content=schema)


_SWAGGER_HTML = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>MediRide API Docs</title>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link rel="stylesheet" type="text/css"
              href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
    </head>
    <body>
        <div id="swagger-ui"></div>
        <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
        <script>
        SwaggerUIBundle({
            url: "/docs/openapi.json",
            dom_id: '#swagger-ui',
            presets: [
                SwaggerUIBundle.presets.apis,
            ],
            deepLinking: true,
            persistAuthorization: true,
            filter: true,
            tagsSorter: "alpha",
        })
        </script>
    </body>
    </html>
"""


@router.get("", include_in_schema=False)
async def docs_root():
    """Swagger UI at /docs."""
    return HTMLResponse(content=_SWAGGER_HTML)


@router.get("/", include_in_schema=False)
async def docs_root_slash():
    """Swagger UI at /docs/."""
    return HTMLResponse(content=_SWAGGER_HTML)


@router.get("/docs", include_in_schema=False)
async def unified_swagger_ui():
    """Swagger UI at /docs/docs (legacy path)."""
    return HTMLResponse(content=_SWAGGER_HTML)


_REDOC_HTML = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>MediRide API Docs</title>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700"
              rel="stylesheet">
        <style> body { margin: 0; padding: 0; } </style>
    </head>
    <body>
        <redoc spec-url='/docs/openapi.json'></redoc>
        <script src="https://unpkg.com/redoc@latest/bundles/redoc.standalone.js"></script>
    </body>
    </html>
"""


@router.get("/redoc", include_in_schema=False)
async def unified_redoc():
    """Unified ReDoc for all MediRide services."""
    return HTMLResponse(content=_REDOC_HTML)
