import pytest

from app import config
from app.utils.files import attachment


def test_attachment_escapes_everything_in_extended_name():
    value = attachment('a/b "c".pdf')
    assert 'filename="a/b _c_.pdf"' in value
    assert "filename*=UTF-8''a%2Fb%20%22c%22.pdf" in value


def test_attachment_strips_control_characters_from_fallback():
    value = attachment("evil\r\nX-Injected: 1.pdf")
    assert "\r" not in value and "\n" not in value


@pytest.mark.parametrize("raw", ["0", "-5", "abc"])
def test_int_env_rejects_invalid_values(monkeypatch, raw):
    monkeypatch.setenv("SOME_LIMIT", raw)
    with pytest.raises(ValueError, match="SOME_LIMIT"):
        config._int_env("SOME_LIMIT", 10)


def test_int_env_uses_default_and_parses(monkeypatch):
    monkeypatch.delenv("SOME_LIMIT", raising=False)
    assert config._int_env("SOME_LIMIT", 10) == 10
    monkeypatch.setenv("SOME_LIMIT", "3")
    assert config._int_env("SOME_LIMIT", 10) == 3
