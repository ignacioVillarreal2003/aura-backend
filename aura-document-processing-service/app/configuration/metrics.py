import logging

logger = logging.getLogger(__name__)

def patch_instrumentator_routing() -> None:
    from prometheus_fastapi_instrumentator import routing
    from starlette.routing import Match

    def _safe_get_route_name(scope, routes, route_name=None):
        for route in routes:
            match, child_scope = route.matches(scope)
            if match == Match.FULL:
                route_name = getattr(route, "path", "") or ""
                child_scope = {**scope, **child_scope}
                sub_routes = getattr(route, "routes", None) or getattr(
                    getattr(route, "router", None), "routes", None
                )
                if sub_routes:
                    child_route_name = _safe_get_route_name(child_scope, sub_routes, route_name)
                    route_name = None if child_route_name is None else route_name + child_route_name
                return route_name or None
            if match == Match.PARTIAL and route_name is None:
                route_name = getattr(route, "path", None)
        return None

    routing._get_route_name = _safe_get_route_name
    logger.info("Patched prometheus-fastapi-instrumentator routing for _IncludedRouter compatibility.")
