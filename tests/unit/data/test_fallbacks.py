from __future__ import annotations

import pytest

import voodoo.data.base as data_base


class _UnexpectedAdapterBug(Exception):
    pass


def test_backend_capability_fallback_does_not_hide_unexpected_adapter_bug(monkeypatch):
    class BrokenAdapter:
        def capabilities(self):
            raise _UnexpectedAdapterBug("adapter implementation failed")

    monkeypatch.setattr(data_base, "_database", BrokenAdapter())
    with pytest.raises(_UnexpectedAdapterBug, match="implementation failed"):
        data_base._backend_uses_identity()
