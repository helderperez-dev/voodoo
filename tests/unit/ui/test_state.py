"""Tests for the state() reactive primitive."""

import pytest

from voodoo import State, state


def test_state_get_initial():
    s = state(42)
    assert s.get() == 42


def test_state_set():
    s = state(0)
    s.set(10)
    assert s.get() == 10


def test_state_update():
    s = state(5)
    s.update(lambda x: x + 3)
    assert s.get() == 8


def test_state_update_with_non_callable():
    s = state(0)
    with pytest.raises(Exception, match="callable"):
        s.update("not a function")


def test_state_subscribe_called_on_set():
    s = state(0)
    received = []
    s.subscribe(lambda v: received.append(v))
    s.set(1)
    s.set(2)
    assert received == [1, 2]


def test_state_unsubscribe():
    s = state(0)
    received = []
    unsub = s.subscribe(lambda v: received.append(v))
    s.set(1)
    unsub()
    s.set(2)
    assert received == [1]


def test_state_subscribe_does_not_raise_on_handler_error():
    s = state(0)

    def bad_handler(v):
        raise RuntimeError("boom")

    s.subscribe(bad_handler)
    s.set(1)  # should not raise


def test_state_set_same_value_still_notifies():
    s = state(5)
    received = []
    s.subscribe(lambda v: received.append(v))
    s.set(5)
    assert received == [5]


def test_state_repr():
    s = state("hello")
    assert repr(s) == "State('hello')"


def test_state_factory_returns_state_instance():
    s = state(None)
    assert isinstance(s, State)


def test_state_default_none():
    s = state()
    assert s.get() is None


def test_state_complex_value():
    s = state({"count": 0})
    s.set({"count": 1})
    assert s.get() == {"count": 1}


def test_state_multiple_subscribers():
    s = state(0)
    a = []
    b = []
    s.subscribe(lambda v: a.append(v))
    s.subscribe(lambda v: b.append(v))
    s.set(1)
    assert a == [1]
    assert b == [1]


def test_state_unsubscribe_twice_safe():
    s = state(0)

    def fn(v):
        return None

    s.subscribe(fn)
    s._unsubscribe(fn)
    s._unsubscribe(fn)  # should not raise
