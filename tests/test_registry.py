from __future__ import annotations

import pytest

from pipeline.core.exceptions import RegistryError
from pipeline.core.registry import Registry


def test_register_and_create():
    reg: Registry[object] = Registry("thing")

    @reg.register("Widget")
    class Widget:
        def __init__(self, size: int = 1) -> None:
            self.size = size

    assert "widget" in reg
    assert reg.available() == ["widget"]
    obj = reg.create("widget", size=3)
    assert isinstance(obj, Widget)
    assert obj.size == 3


def test_duplicate_registration_raises():
    reg: Registry[object] = Registry("thing")

    @reg.register("dup")
    class A:  # noqa: D401
        pass

    with pytest.raises(RegistryError):

        @reg.register("dup")
        class B:  # noqa: D401
            pass


def test_unknown_lookup_raises():
    reg: Registry[object] = Registry("thing")
    with pytest.raises(RegistryError, match="Unknown thing 'nope'"):
        reg.get("nope")
