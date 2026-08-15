import inspect
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.routing import Route


class API:
    def __init__(self) -> None:
        self.routes: list[Route] = []
        self.paths: dict[str, dict[str, Any]] = {}

        # Add docs routes
        self.routes.append(
            Route("/openapi.json", self._openapi_schema, methods=["GET"])
        )
        self.routes.append(Route("/docs", self._swagger_ui, methods=["GET"]))
        self.routes.append(Route("/redoc", self._redoc_ui, methods=["GET"]))

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

    def _add_route(self, path: str, method: str, func: Callable[..., Any]) -> None:  # noqa: C901
        # Register in OpenAPI paths
        if path not in self.paths:
            self.paths[path] = {}

        self.paths[path][method.lower()] = {
            "summary": func.__name__.replace("_", " ").title(),
            "responses": {"200": {"description": "Successful Response"}},
        }

        async def endpoint(request: Request) -> Response:  # noqa: C901
            sig = inspect.signature(func)
            kwargs: dict[str, Any] = {}

            for name, param in sig.parameters.items():
                if param.annotation is Request or name == "request":
                    kwargs[name] = request
                elif name == "user" or (
                    param.annotation is not inspect._empty
                    and getattr(param.annotation, "__name__", "")
                    in ("AuthUser", "User")
                ):
                    from voodoo.auth import get_current_user

                    kwargs[name] = get_current_user(request)
                elif inspect.isclass(param.annotation) and issubclass(
                    param.annotation, BaseModel
                ):
                    # Parse JSON body using Pydantic
                    try:
                        body: Any = await request.json()
                    except Exception:
                        body = {}

                    model_cls: type[BaseModel] = param.annotation
                    if isinstance(body, dict):
                        kwargs[name] = model_cls(**body)
                    elif hasattr(model_cls, "model_validate"):
                        kwargs[name] = model_cls.model_validate(body)
                    else:
                        kwargs[name] = model_cls(**body)
                else:
                    # Path or Query param
                    val: Any = None
                    if name in request.path_params:
                        val = request.path_params[name]
                    elif name in request.query_params:
                        val = request.query_params[name]

                    if val is not None:
                        ann: Any = param.annotation
                        if ann is not inspect._empty and callable(ann):
                            try:
                                val = ann(val)
                            except (ValueError, TypeError):
                                pass
                        kwargs[name] = val

            if inspect.iscoroutinefunction(func):
                res = await func(**kwargs)
            else:
                res = func(**kwargs)

            # Serialize response
            if isinstance(res, Response):
                return res
            elif isinstance(res, BaseModel):
                return JSONResponse(res.model_dump())
            elif (
                isinstance(res, list) and len(res) > 0 and isinstance(res[0], BaseModel)
            ):
                return JSONResponse([r.model_dump() for r in res])
            elif hasattr(res, "__dict__"):  # simple object serialization fallback
                return JSONResponse(res.__dict__)

            return JSONResponse(res)

        # Convert FastAPI/Starlette style path params {id} to Starlette path syntax
        # Actually, Starlette uses {id} or {id:int}, so it's compatible.
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


api = API()
