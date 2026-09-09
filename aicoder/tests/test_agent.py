import os

from aicoder.agent import Agent, _parse_args, _ArgError
from tests.conftest import FakeClient, text_chunks, tool_call_chunks


def approve_all(tool, args):
    return True


def deny_all(tool, args):
    return False


def make_agent(config, scripted, approver=approve_all):
    return Agent(config, approver, client=FakeClient(scripted_responses=scripted))


def test_parse_args():
    assert _parse_args("") == {}
    assert _parse_args('{"a": 1}') == {"a": 1}
    assert isinstance(_parse_args("{bad json"), _ArgError)
    assert isinstance(_parse_args("[1,2]"), _ArgError)  # not an object


def test_full_turn_with_tool_call(config):
    with open(os.path.join(config.workdir, "a.py"), "w") as f:
        f.write("hello\n")

    scripted = [
        tool_call_chunks(0, "call_1", "read_file", '{"path": "a.py"}'),
        text_chunks("done"),
    ]
    agent = make_agent(config, scripted)
    agent.send("read a.py")

    roles = [m["role"] for m in agent.messages]
    assert roles == ["system", "user", "assistant", "tool", "assistant"]
    # the tool message carries the file contents
    tool_msg = agent.messages[3]
    assert tool_msg["tool_call_id"] == "call_1"
    assert tool_msg["content"] == "hello\n"
    # the assistant's final answer
    assert agent.messages[4]["content"] == "done"


def test_assistant_tool_call_message_shape(config):
    with open(os.path.join(config.workdir, "a.py"), "w") as f:
        f.write("x")
    scripted = [
        tool_call_chunks(0, "call_1", "read_file", '{"path": "a.py"}'),
        text_chunks("ok"),
    ]
    agent = make_agent(config, scripted)
    agent.send("go")
    assistant = agent.messages[2]
    assert assistant["tool_calls"][0]["function"]["name"] == "read_file"
    assert assistant["tool_calls"][0]["id"] == "call_1"


def test_declined_mutating_tool(config):
    scripted = [
        tool_call_chunks(0, "call_1", "write_file", '{"path": "x.txt", "content": "hi"}'),
        text_chunks("understood"),
    ]
    agent = make_agent(config, scripted, approver=deny_all)
    agent.send("write a file")
    assert "declined" in agent.messages[3]["content"]
    # the file must NOT have been written
    assert not os.path.exists(os.path.join(config.workdir, "x.txt"))


def test_auto_approve_skips_prompt(config):
    config.auto_approve = True
    scripted = [
        tool_call_chunks(0, "c1", "write_file", '{"path": "y.txt", "content": "hi"}'),
        text_chunks("done"),
    ]
    # deny_all would block, but auto_approve should bypass the approver entirely
    agent = make_agent(config, scripted, approver=deny_all)
    agent.send("write y")
    assert os.path.exists(os.path.join(config.workdir, "y.txt"))


def test_run_tool_unknown(config):
    agent = make_agent(config, [])
    out = agent._run_tool("id1", "does_not_exist", "{}")
    assert "unknown tool" in out


def test_run_tool_bad_json(config):
    agent = make_agent(config, [])
    out = agent._run_tool("id1", "read_file", "{not json")
    assert "could not parse tool arguments" in out


def test_stream_once_accumulates_mixed(config):
    # one response containing both text and a fragmented tool call
    part1_text = text_chunks("thinking... ")[0]
    tc = tool_call_chunks(0, "c9", "git_status", "{}")
    agent = make_agent(config, [[part1_text, *tc]])
    agent.messages.append({"role": "user", "content": "status"})
    text, calls = agent._stream_once()
    assert text == "thinking... "
    assert calls[0]["name"] == "git_status"
    assert calls[0]["id"] == "c9"


def test_no_model_selected(config):
    config.model = None
    agent = make_agent(config, [])
    import pytest
    from aicoder.agent import AgentError
    with pytest.raises(AgentError, match="No model selected"):
        agent.send("hi")


def test_reset(config):
    agent = make_agent(config, [text_chunks("hi")])
    agent.send("hello")
    assert len(agent.messages) > 1
    agent.reset()
    assert len(agent.messages) == 1
    assert agent.messages[0]["role"] == "system"
