import pytest

from app.application.processors.text_cleaners.constants.text_cleaner_type import TextCleanerType
from app.application.processors.text_cleaners.exceptions.text_cleaner_exception import (
    UnsupportedTextCleanerTypeException,
)
from app.application.processors.text_cleaners import text_cleaner_factory as text_cleaner_factory_mod
from app.application.processors.text_cleaners.text_cleaner_factory import TextCleanerFactory
from app.application.processors.text_cleaners.text_cleaner_settings import TextCleanerSettings


def test_factory_returns_simple_cleaner() -> None:
    settings = TextCleanerSettings(active_type=TextCleanerType.simple)
    factory = TextCleanerFactory(text_cleaner_settings=settings)
    c1 = factory.cleaner
    c2 = factory.cleaner
    assert c1 is c2
    assert c1.clean_text("  hi  ") == "hi"


def test_get_by_type_simple() -> None:
    factory = TextCleanerFactory(
        text_cleaner_settings=TextCleanerSettings(active_type=TextCleanerType.simple)
    )
    inst = factory.get_by_type(TextCleanerType.simple)
    assert inst.clean_text("x") == "x"


def test_available_types_contains_simple() -> None:
    factory = TextCleanerFactory(
        text_cleaner_settings=TextCleanerSettings(active_type=TextCleanerType.simple)
    )
    assert TextCleanerType.simple in factory.available_types()


def test_is_supported_simple() -> None:
    factory = TextCleanerFactory(
        text_cleaner_settings=TextCleanerSettings(active_type=TextCleanerType.simple)
    )
    assert factory.is_supported(TextCleanerType.simple) is True


def test_get_active_type() -> None:
    factory = TextCleanerFactory(
        text_cleaner_settings=TextCleanerSettings(active_type=TextCleanerType.simple)
    )
    assert factory.get_active_type() == TextCleanerType.simple


def test_get_by_type_returns_cached_instance() -> None:
    factory = TextCleanerFactory(
        text_cleaner_settings=TextCleanerSettings(active_type=TextCleanerType.simple)
    )
    a = factory.get_by_type(TextCleanerType.simple)
    b = factory.get_by_type(TextCleanerType.simple)
    assert a is b


def test_get_by_type_invalid_type_raises() -> None:
    factory = TextCleanerFactory(
        text_cleaner_settings=TextCleanerSettings(active_type=TextCleanerType.simple)
    )
    with pytest.raises(UnsupportedTextCleanerTypeException):
        factory.get_by_type(object())  # type: ignore[arg-type]


def test_get_by_type_raises_when_registry_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(text_cleaner_factory_mod, "_TEXT_CLEANER_REGISTRY", {})
    factory = TextCleanerFactory(
        text_cleaner_settings=TextCleanerSettings(active_type=TextCleanerType.simple)
    )
    with pytest.raises(UnsupportedTextCleanerTypeException):
        factory.get_by_type(TextCleanerType.simple)
