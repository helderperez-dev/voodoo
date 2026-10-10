from __future__ import annotations

import json

import pytest
from pydantic import BaseModel, ValidationError

from voodoo.routing.api import API


class Payload(BaseModel):
    name: str


class _MalformedRequest:
    async def json(self):
        raise json.JSONDecodeError("malformed", "{", 1)


class _BrokenRequest:
    async def json(self):
        raise RuntimeError("parser implementation failed")


@pytest.mark.asyncio
async def test_model_argument_treats_malformed_json_as_empty_body():
    with pytest.raises(ValidationError):
        await API()._model_argument(_MalformedRequest(), Payload)


@pytest.mark.asyncio
async def test_model_argument_does_not_hide_unexpected_parser_failures():
    with pytest.raises(RuntimeError, match="implementation failed"):
        await API()._model_argument(_BrokenRequest(), Payload)


def test_api_config_resolution_does_not_hide_unexpected_failures(monkeypatch):
    import importlib

    config_mod = importlib.import_module("voodoo.config")

    class BrokenConfig:
        @property
        def runtime(self):
            raise RuntimeError("configuration implementation failed")

    monkeypatch.setattr(config_mod, "config", BrokenConfig())
    with pytest.raises(RuntimeError, match="implementation failed"):
        API()
