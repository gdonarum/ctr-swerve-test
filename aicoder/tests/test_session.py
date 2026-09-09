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
