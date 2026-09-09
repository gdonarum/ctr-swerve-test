import builtins

from aicoder import ui


def _force_plain(monkeypatch):
    # force the plain (non-rich) input path so we can drive builtins.input
    monkeypatch.setattr(ui, "_console", None)


def test_confirm_default_yes(monkeypatch):
    _force_plain(monkeypatch)
    monkeypatch.setattr(builtins, "input", lambda prompt="": "")  # just Enter
    assert ui.confirm("q?") is True
    assert ui.confirm("q?", default=False) is False


def test_confirm_explicit(monkeypatch):
    _force_plain(monkeypatch)
    monkeypatch.setattr(builtins, "input", lambda prompt="": "n")
    assert ui.confirm("q?") is False
    monkeypatch.setattr(builtins, "input", lambda prompt="": "yes")
    assert ui.confirm("q?", default=False) is True


def test_approve_values(monkeypatch):
    _force_plain(monkeypatch)
    cases = {"": "yes", "y": "yes", "yes": "yes", "a": "always", "always": "always", "n": "no", "no": "no"}
    for typed, expected in cases.items():
        monkeypatch.setattr(builtins, "input", lambda prompt="", _t=typed: _t)
        assert ui.approve("q") == expected


def test_splash_uses_working_group_tagline():
    assert "AI for Software Engineers Working Group" in ui.TAGLINE
