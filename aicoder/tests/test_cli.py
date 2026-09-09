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
