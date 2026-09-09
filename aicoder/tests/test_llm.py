import pytest

from aicoder import llm
from aicoder.config import Config
from tests.conftest import FakeClient


def test_make_client_requires_credentials():
    with pytest.raises(llm.LLMError, match="not configured"):
        llm.make_client(Config())


def test_list_models_sorted():
    client = FakeClient(models=["zebra", "alpha", "mango"])
    assert llm.list_models(client) == ["alpha", "mango", "zebra"]


def test_list_models_wraps_errors():
    class Boom:
        @property
        def models(self):
            raise RuntimeError("down")

    with pytest.raises(llm.LLMError, match="Could not list models"):
        llm.list_models(Boom())
