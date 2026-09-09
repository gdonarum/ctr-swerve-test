from aicoder import cli
from aicoder.agent import Agent
from aicoder.config import Config
from tests.conftest import FakeClient


def make_agent(models=None, **cfg_kwargs):
    config = Config(base_url="u", api_key="k", model="test-model", **cfg_kwargs)
    client = FakeClient(models=models or ["test-model", "another-model"])
    return Agent(config, lambda t, a: True, client=client)


def test_parser_one_shot():
    args = cli._build_parser().parse_args(["hello", "world", "--model", "m"])
    assert args.prompt == ["hello", "world"]
    assert args.model == "m"


def test_parser_flags():
    args = cli._build_parser().parse_args(["-y", "--workdir", "/x"])
    assert args.yes is True
    assert args.workdir == "/x"
    assert args.prompt == []


def test_language_for():
    assert cli._language_for("a.py") == "python"
    assert cli._language_for("b.ts") == "typescript"
    assert cli._language_for("c.unknown") == "text"


def test_handle_slash_exit_returns_false():
    agent = make_agent()
    assert cli._handle_slash(agent, "/exit") is False
    assert cli._handle_slash(agent, "/quit") is False


def test_handle_slash_reset():
    agent = make_agent()
    agent.messages.append({"role": "user", "content": "x"})
    assert cli._handle_slash(agent, "/reset") is True
    assert len(agent.messages) == 1


def test_handle_slash_model_set():
    agent = make_agent()
    assert cli._handle_slash(agent, "/model another-model") is True
    assert agent.config.model == "another-model"


def test_handle_slash_model_unknown_rejected():
    agent = make_agent()
    cli._handle_slash(agent, "/model bogus")
    assert agent.config.model == "test-model"  # unchanged


def test_handle_slash_models_runs():
    agent = make_agent()
    assert cli._handle_slash(agent, "/models") is True


def test_handle_slash_unknown_command():
    agent = make_agent()
    assert cli._handle_slash(agent, "/nope") is True


def test_handle_slash_commit_requires_message():
    agent = make_agent()
    # empty message returns before any confirmation prompt
    assert cli._handle_slash(agent, "/commit") is True


def test_handle_slash_issues_without_gitlab(capsys):
    agent = make_agent()
    assert cli._handle_slash(agent, "/issues") is True
    # gitlab not configured -> an error is surfaced, no crash
    err = capsys.readouterr().err
    assert "GitLab is not configured" in err


def test_main_without_credentials(monkeypatch):
    for var in [
        "LITELLM_BASE_URL", "LITELLM_API_KEY", "AICODER_BASE_URL", "AICODER_API_KEY",
        "OPENAI_BASE_URL", "OPENAI_API_KEY", "LITELLM_MODEL", "AICODER_MODEL",
    ]:
        monkeypatch.delenv(var, raising=False)
    assert cli.main([]) == 2


def test_main_bad_workdir(monkeypatch):
    monkeypatch.setenv("LITELLM_BASE_URL", "https://x.test")
    monkeypatch.setenv("LITELLM_API_KEY", "sk-x")
    assert cli.main(["--workdir", "/definitely/not/here", "hi"]) == 2


def test_parser_tls_flags():
    args = cli._build_parser().parse_args(["--ca-bundle", "/x/ca.pem", "--system-certs"])
    assert args.ca_bundle == "/x/ca.pem"
    assert args.system_certs is True


def test_handle_slash_mrs_without_gitlab(capsys):
    agent = make_agent()
    assert cli._handle_slash(agent, "/mrs") is True
    assert "GitLab is not configured" in capsys.readouterr().err


def test_handle_slash_save_resume_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("AICODER_SESSIONS_DIR", str(tmp_path))
    agent = make_agent()
    agent.messages.append({"role": "user", "content": "remember me"})
    assert cli._handle_slash(agent, "/save mysess") is True

    # change history, then resume should restore it
    agent.messages.append({"role": "user", "content": "throwaway"})
    assert cli._handle_slash(agent, "/resume mysess") is True
    assert agent.messages[-1]["content"] == "remember me"


def test_handle_slash_sessions_lists(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("AICODER_SESSIONS_DIR", str(tmp_path))
    agent = make_agent()
    cli._handle_slash(agent, "/save alpha")
    capsys.readouterr()  # clear
    cli._handle_slash(agent, "/sessions")
    assert "alpha" in capsys.readouterr().out


def test_handle_slash_resume_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("AICODER_SESSIONS_DIR", str(tmp_path))
    agent = make_agent()
    cli._handle_slash(agent, "/resume ghost")
    assert "No saved session" in capsys.readouterr().err


def test_parser_continue_and_no_autosave():
    args = cli._build_parser().parse_args(["-c", "--no-autosave"])
    assert args.continue_ is True
    assert args.no_autosave is True


def test_autosave_writes_and_resumes(tmp_path, monkeypatch):
    from aicoder import session
    monkeypatch.setenv("AICODER_SESSIONS_DIR", str(tmp_path))
    agent = make_agent(workdir=str(tmp_path))
    agent.messages.append({"role": "user", "content": "keep me"})
    cli._autosave(agent)
    assert session.has_autosave(str(tmp_path))

    # /resume with no name restores this workdir's autosave
    fresh = make_agent(workdir=str(tmp_path))
    cli._handle_slash(fresh, "/resume")
    assert fresh.messages[-1]["content"] == "keep me"


def test_no_autosave_disables(tmp_path, monkeypatch):
    from aicoder import session
    monkeypatch.setenv("AICODER_SESSIONS_DIR", str(tmp_path))
    agent = make_agent(workdir=str(tmp_path), autosave=False)
    agent.messages.append({"role": "user", "content": "x"})
    cli._autosave(agent)
    assert session.has_autosave(str(tmp_path)) is False


def test_splash_and_banner_do_not_crash():
    # smoke test the branded splash/banner rendering
    ui = __import__("aicoder.ui", fromlist=["ui"])
    ui.splash()
    ui.banner("m", "/w", hint="hi")


def _write_tool():
    from aicoder import tools
    return tools.get_tool("write_file")


def test_approver_default_yes(monkeypatch):
    from aicoder import ui
    monkeypatch.setattr(ui, "diff_preview", lambda *a, **k: None)
    monkeypatch.setattr(ui, "approve", lambda q: "yes")
    approver = cli._make_approver(Config())
    assert approver(_write_tool(), {"path": "a", "content": "x"}) is True


def test_approver_no(monkeypatch):
    from aicoder import ui
    monkeypatch.setattr(ui, "diff_preview", lambda *a, **k: None)
    monkeypatch.setattr(ui, "approve", lambda q: "no")
    approver = cli._make_approver(Config())
    assert approver(_write_tool(), {"path": "a", "content": "x"}) is False


def test_approver_always_is_sticky(monkeypatch):
    from aicoder import ui
    prompts = []
    monkeypatch.setattr(ui, "diff_preview", lambda *a, **k: None)
    monkeypatch.setattr(ui, "info", lambda *a, **k: None)
    monkeypatch.setattr(ui, "approve", lambda q: prompts.append(q) or "always")
    approver = cli._make_approver(Config())
    tool = _write_tool()
    assert approver(tool, {"path": "a", "content": "1"}) is True
    assert approver(tool, {"path": "b", "content": "2"}) is True
    # only prompted once; the second call was auto-approved
    assert len(prompts) == 1


def test_approver_always_is_per_tool(monkeypatch):
    from aicoder import tools, ui
    monkeypatch.setattr(ui, "diff_preview", lambda *a, **k: None)
    monkeypatch.setattr(ui, "info", lambda *a, **k: None)
    seen = []
    monkeypatch.setattr(ui, "approve", lambda q: seen.append(q) or "always")
    approver = cli._make_approver(Config())
    approver(tools.get_tool("write_file"), {"path": "a", "content": "1"})
    # a different tool still prompts (stickiness is per tool type)
    approver(tools.get_tool("run_command"), {"command": "ls"})
    assert len(seen) == 2
