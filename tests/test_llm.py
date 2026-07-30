import json

from causeforge.runtime.llm import DiskCachedLLM, LLMResponse
from causeforge.runtime.llm_policy import LLMPolicy, extract_action
from causeforge.sdk.schemas import Step, ToolCall


class FakeClient:
    model = "fake-model"

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0

    def params(self):
        return {"model": self.model, "temperature": 0.0}

    def complete(self, messages):
        self.calls += 1
        return LLMResponse(text=self.replies.pop(0), tokens_in=10, tokens_out=5,
                           dollars=0.001)


def test_extract_action_variants():
    assert extract_action('{"tool": "run_pytest", "args": {}}')["tool"] == "run_pytest"
    fenced = 'Sure!\n```json\n{"tool": "write_file", "args": {"path": "a.py", "content": "x = \\"{\\"\\n"}}\n```'
    action = extract_action(fenced)
    assert action["args"]["path"] == "a.py" and "{" in action["args"]["content"]
    assert extract_action("no json here") is None
    assert extract_action('{"not_a_tool": 1}') is None


def test_disk_cache_hit_is_free_and_stable(tmp_path):
    client = FakeClient(['{"tool": "done", "args": {}}'])
    llm = DiskCachedLLM(client, tmp_path / "cache")
    messages = [{"role": "user", "content": "hi"}]
    first = llm.complete(messages)
    second = llm.complete(messages)  # would raise IndexError if it hit the client
    assert client.calls == 1
    assert not first.cached and second.cached
    assert second.dollars == 0.0 and first.dollars > 0
    assert second.text == first.text


def test_llm_policy_step_and_termination():
    client = FakeClient([
        '{"tool": "write_file", "args": {"path": "solution.py", "content": "x = 1\\n"}}',
        '{"tool": "done", "args": {}}',
    ])
    policy = LLMPolicy(client, max_steps=5)
    policy.bind_task("implement x")

    action, record = policy.next_action("t", 0, [])
    assert action == ToolCall(tool="write_file", args={"path": "solution.py", "content": "x = 1\n"})
    assert record.model == "fake-model" and not record.cached

    history = [Step(index=0, action=action, observation="wrote solution.py")]
    assert policy.next_action("t", 1, history) is None  # "done" ends the episode

    # history is rendered into the conversation
    sent = json.loads(record.prompt)
    assert sent[0]["role"] == "system" and "implement x" in sent[1]["content"]


def test_llm_policy_respects_max_steps():
    policy = LLMPolicy(FakeClient([]), max_steps=0)
    policy.bind_task("t")
    assert policy.next_action("t", 0, []) is None  # client never called
