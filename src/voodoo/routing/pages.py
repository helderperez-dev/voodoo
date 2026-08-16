"""Routing primitives.

`page(path)` registers an SSR HTML route; the shared :func:`call_page` helper
implements handler invocation (dependency injection, sync/async dispatch,
result rendering) for both decorator-registered and file-based pages.
"""

import inspect
from collections.abc import Callable
from typing import Any

from starlette.requests import Request
from starlette.responses import HTMLResponse, Response
from starlette.routing import Route


class PageRegistry:
    """Registry of routes declared with the ``@page`` decorator."""

    def __init__(self) -> None:
        self._routes: list[Route] = []

    def add(self, route: Route) -> Route:
        self._routes.append(route)
        return route

    @property
    def routes(self) -> list[Route]:
        return list(self._routes)

    def clear(self) -> None:
        """Remove all registered pages (test isolation)."""
        self._routes.clear()


page_registry = PageRegistry()


def page(path: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Register a page (SSR HTML route) for a ``GET`` request.

    Works with sync and async handlers. The handler may return a Component,
    a plain string, a ``(SEO, Component)`` tuple, or a Starlette ``Response``
    (returned untouched). Dynamic path parameters are injected by name and
    coerced to their signature annotation when possible::

        @page("/users/{id}")
        async def user(id: int):
            return Card(Text(f"User {id}"))
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        route = Route(path, _page_endpoint(func), methods=["GET"])
        page_registry.add(route)
        func.voodoo_path = path  # type: ignore[attr-defined]
        return func

    return decorator


def _page_endpoint(func: Callable[..., Any]) -> Callable:
    async def endpoint(request: Request) -> Response:
        return await call_page(func, request)

    return endpoint


async def call_page(func: Callable[..., Any], request: Request) -> Response:
    """Invoke a page handler and render its result into an HTTP response."""
    sig = inspect.signature(func)
    kwargs: dict[str, Any] = {}

    # Inject request if requested
    if "request" in sig.parameters:
        kwargs["request"] = request

    # Inject user if requested
    if "user" in sig.parameters:
        from voodoo.auth import get_current_user

        kwargs["user"] = get_current_user(request)

    # Inject dynamic path parameters with type coercion if annotated
    for param, val in request.path_params.items():
        if param in sig.parameters:
            param_type = sig.parameters[param].annotation
            if param_type is not inspect._empty and callable(param_type):
                try:
                    val = param_type(val)
                except (ValueError, TypeError):
                    pass
            kwargs[param] = val

    result = func(**kwargs)
    if inspect.iscoroutine(result):
        result = await result

    return render_page_result(result)


def render_page_result(result: Any) -> Response:
    """Convert a page handler's return value into an HTTP response."""
    if isinstance(result, Response):
        return result

    from voodoo.seo import SEO
    from voodoo.ui.rendering import render_page

    # Detect (SEO, Component) or (Component, SEO) tuple vs plain Component
    seo = None
    component = result
    if isinstance(result, tuple) and len(result) == 2:
        first, second = result
        if isinstance(first, SEO):
            seo = first
            component = second
        elif isinstance(second, SEO):
            seo = second
            component = first

    return HTMLResponse(render_page(component, seo=seo))
