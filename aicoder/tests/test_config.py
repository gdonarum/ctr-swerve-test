from aicoder.config import Config


def test_from_env_reads_litellm_vars(monkeypatch):
    monkeypatch.setenv("LITELLM_BASE_URL", "https://a.test")
    monkeypatch.setenv("LITELLM_API_KEY", "sk-a")
    monkeypatch.setenv("LITELLM_MODEL", "m1")
    cfg = Config.from_env()
    assert cfg.base_url == "https://a.test"
    assert cfg.api_key == "sk-a"
    assert cfg.model == "m1"
    assert cfg.has_llm_credentials()


def test_from_env_fallback_names(monkeypatch):
    monkeypatch.delenv("LITELLM_BASE_URL", raising=False)
    monkeypatch.delenv("LITELLM_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_BASE_URL", "https://o.test")
    monkeypatch.setenv("AICODER_API_KEY", "sk-fallback")
    cfg = Config.from_env()
    assert cfg.base_url == "https://o.test"
    assert cfg.api_key == "sk-fallback"


def test_overrides_ignore_none(monkeypatch):
    monkeypatch.setenv("LITELLM_MODEL", "keep")
    cfg = Config.from_env(model=None, workdir="/tmp")
    assert cfg.model == "keep"
    assert cfg.workdir == "/tmp"


def test_gitlab_credentials_predicate():
    assert not Config().has_gitlab_credentials()
    assert Config(gitlab_url="u", gitlab_token="t").has_gitlab_credentials()


def test_llm_credentials_requires_both():
    assert not Config(base_url="u").has_llm_credentials()
    assert not Config(api_key="k").has_llm_credentials()
    assert Config(base_url="u", api_key="k").has_llm_credentials()
