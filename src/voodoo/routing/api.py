import inspect
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.routing import Route


def _default_run_through_runtime() -> bool:
    """Resolve the default ``run_through_runtime`` value from config, falling
    back to ``True`` when config cannot be loaded (e.g. before app bootstrap).
    """
    try:
        from voodoo.config import config

        return bool(config.runtime.run_api_through_runtime)
    except Exception:
        return True


class API:
    def __init__(self) -> None:
        self.routes: list[Route] = []
        self.paths: dict[str, dict[str, Any]] = {}
        # When True (default), every API handler executes through the Voodoo
        # runtime engine, producing an Execution record (intent ``http:...``)
        # with actor, effects, cost and telemetry. Configurable via the
        # ``runtime.run_api_through_runtime`` config flag (or the
        # ``VOODOO_RUN_API_THROUGH_RUNTIME`` env var); the attribute remains
        # mutable for per-app overrides.
        self.run_through_runtime: bool = _default_run_through_runtime()

        # Add docs routes
        self.routes.append(
            Route("/openapi.json", self._openapi_schema, methods=["GET"])
        )
        self.routes.append(Route("/docs", self._swagger_ui, methods=["GET"]))
        self.routes.append(Route("/redoc", self._redoc_ui, methods=["GET"]))

    async def _run_through_runtime(
        self, path: str, method: str, func: Callable[..., Any], kwargs: dict[str, Any]
    ) -> Any:
        """Execute an API handler through the runtime engine.

        The handler becomes an Execution (intent ``http:{method} {path}``);
        the authenticated user (if any) is the actor. The handler's return
        value is the execution result.
        """
        if not self.run_through_runtime:
            if inspect.iscoroutinefunction(func):
                return await func(**kwargs)
            return func(**kwargs)

        from voodoo.primitives.intent import Intent
        from voodoo.runtime.engine import engine as runtime_engine

        actor = "anonymous"
        user = kwargs.get("user")
        if user is not None:
            actor = (
                getattr(user, "id", None) or getattr(user, "username", None) or actor
            )

        intent = Intent(
            name=f"http:{method} {path}",
            params={k: v for k, v in kwargs.items() if k != "request"},
        )

        async def compute(ctx: Any) -> Any:
            if inspect.iscoroutinefunction(func):
                return await func(**kwargs)
            return func(**kwargs)

        execution = await runtime_engine.execute(intent, compute, actor=actor)
        return execution.result

    def _openapi_schema(self, request: Request) -> JSONResponse:
        schema = {
            "openapi": "3.0.2",
            "info": {"title": "Voodoo API", "version": "1.0.0"},
            "paths": self.paths,
            "components": {
                "schemas": {},
                "securitySchemes": {
                    "bearerAuth": {
                        "type": "http",
                        "scheme": "bearer",
                        "bearerFormat": "JWT",
                        "description": "Provide 'Bearer <token>' in Authorization header",
                    },
                    "apiKeyAuth": {
                        "type": "apiKey",
                        "in": "header",
                        "name": "X-API-Key",
                        "description": "Provide API Key in X-API-Key header",
                    },
                    "cookieAuth": {
                        "type": "apiKey",
                        "in": "cookie",
                        "name": "voodoo_auth",
                        "description": "Session cookie authentication",
                    },
                },
            },
        }
        return JSONResponse(schema)

    def _swagger_ui(self, request: Request) -> HTMLResponse:
        html = """
        <!DOCTYPE html>
        <html>
        <head>
        <title>Swagger UI</title>
        <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5.0.0/swagger-ui.css" />
        </head>
        <body>
        <div id="swagger-ui"></div>
        <script src="https://unpkg.com/swagger-ui-dist@5.0.0/swagger-ui-bundle.js"></script>
        <script>
        window.onload = () => {
            window.ui = SwaggerUIBundle({
                url: '/openapi.json',
                dom_id: '#swagger-ui',
            });
        };
        </script>
        </body>
        </html>
        """
        return HTMLResponse(html)

    def _redoc_ui(self, request: Request) -> HTMLResponse:
        html = """
        <!DOCTYPE html>
        <html>
        <head>
        <title>ReDoc</title>
        </head>
        <body>
        <redoc spec-url='/openapi.json'></redoc>
        <script src="https://unpkg.com/redoc@2.0.0-rc.53/bundles/redoc.standalone.js"></script>
        </body>
        </html>
        """
        return HTMLResponse(html)

    async def _model_argument(self, request: Request, model_cls: type[BaseModel]) -> BaseModel:
        try:
            body: Any = await request.json()
        except Exception:
            body = {}
        if isinstance(body, dict):
            return model_cls(**body)
        if hasattr(model_cls, "model_validate"):
            return model_cls.model_validate(body)
        return model_cls(**body)

    async def _argument_value(self, request: Request, name: str, param: inspect.Parameter) -> Any:
        if param.annotation is Request or name == "request":
            return request
        if name == "user" or (
            param.annotation is not inspect._empty
            and getattr(param.annotation, "__name__", "") in ("AuthUser", "User")
        ):
            from voodoo.auth import get_current_user

            return get_current_user(request)
        if inspect.isclass(param.annotation) and issubclass(param.annotation, BaseModel):
            return await self._model_argument(request, param.annotation)
        value = request.path_params.get(name, request.query_params.get(name))
        annotation: Any = param.annotation
        if value is not None and annotation is not inspect._empty and callable(annotation):
            try:
                return annotation(value)
            except (ValueError, TypeError):
                pass
        return value

    async def _endpoint_kwargs(self, request: Request, func: Callable[..., Any]) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        for name, param in inspect.signature(func).parameters.items():
            value = await self._argument_value(request, name, param)
            if value is not None:
                kwargs[name] = value
        return kwargs

    @staticmethod
    def _serialize_result(result: Any) -> Response:
        if isinstance(result, Response):
            return result
        if isinstance(result, BaseModel):
            return JSONResponse(result.model_dump())
        if isinstance(result, list) and result and isinstance(result[0], BaseModel):
            return JSONResponse([item.model_dump() for item in result])
        if hasattr(result, "__dict__"):
            return JSONResponse(result.__dict__)
        return JSONResponse(result)

    def _register_openapi_route(self, path: str, method: str, func: Callable[..., Any]) -> None:
        self.paths.setdefault(path, {})[method.lower()] = {
            "summary": func.__name__.replace("_", " ").title(),
            "responses": {"200": {"description": "Successful Response"}},
        }

    def _add_route(self, path: str, method: str, func: Callable[..., Any]) -> None:
        self._register_openapi_route(path, method, func)

        async def endpoint(request: Request) -> Response:
            kwargs = await self._endpoint_kwargs(request, func)
            result = await self._run_through_runtime(path, method, func, kwargs)
            return self._serialize_result(result)

        self.routes.append(Route(path, endpoint, methods=[method]))

    def get(self, path: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self._add_route(path, "GET", func)
            return func

        return decorator

    def post(self, path: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self._add_route(path, "POST", func)
            return func

        return decorator

    def put(self, path: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self._add_route(path, "PUT", func)
            return func

        return decorator

    def delete(self, path: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self._add_route(path, "DELETE", func)
            return func

        return decorator

    def patch(self, path: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self._add_route(path, "PATCH", func)
            return func

        return decorator


api = API()
