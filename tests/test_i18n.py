import os
import json
import pytest
from starlette.testclient import TestClient
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import PlainTextResponse

from voodoo.i18n import I18n, _, current_language, I18nMiddleware

@pytest.fixture
def mock_locales(tmp_path):
    locales_dir = tmp_path / "locales"
    locales_dir.mkdir()
    
    en_data = {"hello": "Hello", "nested": {"key": "Value {name}"}}
    pt_data = {"hello": "Olá", "nested": {"key": "Valor {name}"}}
    
    (locales_dir / "en.json").write_text(json.dumps(en_data), encoding="utf-8")
    (locales_dir / "pt.json").write_text(json.dumps(pt_data), encoding="utf-8")
    
    return str(locales_dir)

def test_i18n_loading(mock_locales):
    i18n = I18n(locales_dir=mock_locales)
    
    assert i18n.get_translation("en", "hello") == "Hello"
    assert i18n.get_translation("pt", "hello") == "Olá"
    
    # Fallback to default
    assert i18n.get_translation("es", "hello") == "Hello"
    
    # Missing key
    assert i18n.get_translation("en", "missing.key") == "missing.key"
    
    # Interpolation
    assert i18n.get_translation("en", "nested.key", name="World") == "Value World"
    assert i18n.get_translation("pt", "nested.key", name="Mundo") == "Valor Mundo"

def test_i18n_middleware(mock_locales):
    i18n = I18n(locales_dir=mock_locales)
    
    async def homepage(request):
        # We temporarily override the global i18n_instance in the test
        # but here we can just use the context var directly
        import voodoo.i18n
        voodoo.i18n.i18n_instance = i18n
        
        return PlainTextResponse(f"Lang: {current_language.get()} - Msg: {_('hello')}")
        
    app = Starlette(routes=[Route("/", homepage)])
    app.add_middleware(I18nMiddleware, i18n=i18n)
    
    client = TestClient(app)
    
    # 1. Default
    resp = client.get("/")
    assert resp.text == "Lang: en - Msg: Hello"
    
    # 2. Accept-Language header
    resp = client.get("/", headers={"Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8"})
    assert resp.text == "Lang: pt - Msg: Olá"
    
    # 3. Cookie
    client.cookies = {"voodoo_lang": "pt"}
    resp = client.get("/")
    assert resp.text == "Lang: pt - Msg: Olá"
    
    # 4. Query Param
    resp = client.get("/?lang=en")
    assert resp.text == "Lang: en - Msg: Hello"
    # Query param sets the cookie
    assert "voodoo_lang=en" in resp.headers.get("set-cookie", "")
