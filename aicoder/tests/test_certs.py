import certifi
import pytest

from aicoder import certs, llm
from aicoder.config import Config


def test_requests_verify_default_true():
    assert certs.requests_verify(Config()) is True


def test_requests_verify_uses_bundle():
    assert certs.requests_verify(Config(ca_bundle="/x/ca.pem")) == "/x/ca.pem"


def test_make_client_with_ca_bundle_builds():
    # A configured CA bundle should be accepted and produce a usable client
    # (construction is offline; no request is sent).
    cfg = Config(base_url="https://litellm.test", api_key="sk", ca_bundle=certifi.where())
    client = llm.make_client(cfg)
    assert client is not None


def test_apply_system_certs_disabled():
    assert certs.apply_system_certs(Config(use_system_certs=False)) is False


def test_apply_system_certs_enabled_behaviour():
    cfg = Config(use_system_certs=True)
    try:
        import truststore  # noqa: F401
        available = True
    except ImportError:
        available = False

    if available:
        assert certs.apply_system_certs(cfg) is True
    else:
        with pytest.raises(certs.CertError, match="truststore"):
            certs.apply_system_certs(cfg)
