import pytest

from aicoder import session


@pytest.fixture(autouse=True)
def sessions_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("AICODER_SESSIONS_DIR", str(tmp_path))
    return tmp_path


def test_save_and_load_roundtrip():
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "hi"}]
    name = session.save(msgs, "m1", "/work", "mytest")
    assert name == "mytest"
    data = session.load("mytest")
    assert data["messages"] == msgs
    assert data["model"] == "m1"
    assert data["workdir"] == "/work"


def test_default_name_used_when_missing():
    name = session.save([{"role": "user", "content": "x"}], "m", "/w")
    assert name.startswith("session-")
    assert session.list_sessions() == [name]


def test_list_sessions_multiple():
    session.save([{"role": "user", "content": "a"}], "m", "/w", "one")
    session.save([{"role": "user", "content": "b"}], "m", "/w", "two")
    assert set(session.list_sessions()) == {"one", "two"}


def test_load_missing_raises():
    with pytest.raises(session.SessionError, match="No saved session"):
        session.load("nope")


def test_name_is_sanitized():
    name = session.save([{"role": "user", "content": "x"}], None, "/w", "weird/name!! spaces")
    assert "/" not in name and " " not in name
    assert session.load(name)["model"] is None


def test_delete():
    session.save([{"role": "user", "content": "x"}], "m", "/w", "d1")
    session.delete("d1")
    with pytest.raises(session.SessionError):
        session.load("d1")


def test_load_rejects_payload_without_messages(sessions_tmp):
    (sessions_tmp / "bad.json").write_text('{"model": "m"}', encoding="utf-8")
    with pytest.raises(session.SessionError, match="missing a message history"):
        session.load("bad")


def test_empty_name_rejected():
    with pytest.raises(session.SessionError):
        session.save([{"role": "user", "content": "x"}], "m", "/w", "!!!")


# --- autosave ---------------------------------------------------------------


def test_autosave_name_is_stable_and_workdir_specific():
    assert session.autosave_name("/a") == session.autosave_name("/a")
    assert session.autosave_name("/a") != session.autosave_name("/b")
    assert session.autosave_name("/a").startswith("autosave-")


def test_autosave_roundtrip(tmp_path):
    workdir = str(tmp_path / "proj")
    assert session.has_autosave(workdir) is False
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "hi"}]
    session.autosave(msgs, "m1", workdir)
    assert session.has_autosave(workdir) is True
    data = session.load_autosave(workdir)
    assert data["messages"] == msgs
    assert data["model"] == "m1"


def test_autosave_never_raises(monkeypatch):
    # even if save fails, autosave returns "" instead of raising
    monkeypatch.setattr(session, "save", lambda *a, **k: (_ for _ in ()).throw(session.SessionError("x")))
    assert session.autosave([], None, "/w") == ""
