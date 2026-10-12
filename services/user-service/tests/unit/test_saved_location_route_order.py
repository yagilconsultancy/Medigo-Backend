from app.api.v1.saved_location_endpoints import router


def test_reorder_is_declared_before_the_id_route():
    """FastAPI matches in declaration order, so /reorder must come first or it
    is read as a location id and rejected."""
    put_paths = [
        r.path for r in router.routes if "PUT" in getattr(r, "methods", set())
    ]
    reorder = next(i for i, p in enumerate(put_paths) if p.endswith("/reorder"))
    by_id = next(i for i, p in enumerate(put_paths) if p.endswith("/{location_id}"))
    assert reorder < by_id
