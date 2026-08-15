import json
import os
from contextvars import ContextVar
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# Context variables for the current request's language and translations
current_language: ContextVar[str] = ContextVar("current_language", default="en")
translations: ContextVar[dict[str, Any] | None] = ContextVar(
    "translations", default=None
)


class I18n:
    """Internationalization manager for Voodoo."""

    def __init__(self, default_lang: str = "en", locales_dir: str = "locales"):
        self.default_lang = default_lang
        self.locales_dir = locales_dir
        self.locales: dict[str, dict[str, Any]] = {}
        self.load_locales()

    def load_locales(self):
        """Loads JSON locale files from the locales directory."""
        if not os.path.exists(self.locales_dir):
            return

        for filename in os.listdir(self.locales_dir):
            if filename.endswith(".json"):
                lang = filename[:-5]
                filepath = os.path.join(self.locales_dir, filename)
                try:
                    with open(filepath, encoding="utf-8") as f:
                        self.locales[lang] = json.load(f)
                except Exception as e:
                    print(f"Error loading locale {lang}: {e}")

    def get_translation(self, lang: str, key: str, **kwargs) -> str:
        """Retrieves a translation string by key for a specific language."""
        lang_dict = self.locales.get(lang) or self.locales.get(self.default_lang) or {}

        # Support nested keys like "home.title"
        keys = key.split(".")
        val = lang_dict
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k)
            else:
                val = None
                break

        if val is None:
            return key  # fallback to key if not found

        if isinstance(val, str) and kwargs:
            try:
                return val.format(**kwargs)
            except KeyError:
                return val

        return str(val)


# Global i18n instance
i18n_instance = I18n()


def _(key: str, **kwargs) -> str:
    """
    Translates a key using the current request's language.
    This is the main function to be used in components and pages.
    """
    lang = current_language.get()
    return i18n_instance.get_translation(lang, key, **kwargs)


class I18nMiddleware(BaseHTTPMiddleware):
    """
    Middleware to detect and set the language for the current request.
    Priority: Query Param (?lang=) > Cookie (voodoo_lang) > Accept-Language Header > Default
    """

    def __init__(self, app, i18n: I18n | None = None):
        super().__init__(app)
        self.i18n = i18n or i18n_instance

    async def dispatch(self, request: Request, call_next):
        # 1. Query Param
        lang = request.query_params.get("lang")

        # 2. Cookie
        if not lang:
            lang = request.cookies.get("voodoo_lang")

        # 3. Accept-Language Header
        if not lang:
            accept_lang = request.headers.get("accept-language")
            if accept_lang:
                # e.g., "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
                lang = accept_lang.split(",")[0].split("-")[0]

        if not lang or lang not in self.i18n.locales:
            lang = self.i18n.default_lang

        # Set the context variable for the duration of this request
        token = current_language.set(lang)
        try:
            response = await call_next(request)
            # If lang was set via query, we might want to set a cookie for future requests
            if request.query_params.get("lang"):
                response.set_cookie("voodoo_lang", lang)
            return response
        finally:
            current_language.reset(token)
