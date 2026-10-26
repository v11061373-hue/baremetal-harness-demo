"""baremetal-harness-demo 核心逻辑离线测试（无 API Key，ScriptedModel 回放）。"""
import asyncio

import demo


def test_build_tasks_math_verifier():
    tasks = demo.build_tasks()
    assert len(tasks) == 1
    task = tasks[0]
    assert task.task_id == "math"
    ok = asyncio.run(task.verifier.verify("答案是 42", task.prompt))
    bad = asyncio.run(task.verifier.verify("答案是 6", task.prompt))
    assert ok is None
    assert bad is not None


def test_run_eval_loop_promotes_skill():
    result = asyncio.run(demo.run_eval_loop())
    steps = result["steps"]
    assert steps, "branch_search 至少一个 step"
    assert steps[-1]["promoted"] is not None, "最后一步应 promote 规则"
    assert "42" in result["skill_md"], "SKILL.md 含挖出的规则"


def test_run_self_improve_promotes():
    result = asyncio.run(demo.run_self_improve())
    assert result["baseline"]["math"] is False, "baseline 失败"
    assert result["rule"], "机械挖出规则非空"
    assert result["candidate"]["math"] is True, "候选通过"
    assert result["promote"] is True, "gate 判 promote"
    assert "converted" in result["reason"]


def test_build_tasks_custom_prompt_needle():
    tasks = demo.build_tasks(prompt="2+2?", needle="4")
    assert len(tasks) == 1
    task = tasks[0]
    assert task.prompt == "2+2?"
    assert asyncio.run(task.verifier.verify("答案是 4", task.prompt)) is None
    assert asyncio.run(task.verifier.verify("答案是 5", task.prompt)) is not None


def test_make_runtime_offline(monkeypatch):
    monkeypatch.delenv("BAREMETAL_HARNESS_API_KEY", raising=False)
    provider, model, miner = demo.make_runtime()
    assert isinstance(provider, demo.ScriptedModel)
    assert model == "scripted"
    assert isinstance(miner, demo.ScriptedModel)


def test_make_runtime_live(monkeypatch):
    monkeypatch.setenv("BAREMETAL_HARNESS_API_KEY", "sk-test")
    monkeypatch.delenv("BAREMETAL_HARNESS_BASE_URL", raising=False)
    monkeypatch.delenv("BAREMETAL_HARNESS_MODEL", raising=False)
    provider, model, miner = demo.make_runtime()
    assert isinstance(provider, demo.OpenAICompatibleClient)
    assert model == "deepseek-chat"
    assert miner is provider


def test_run_eval_trace_shape():
    trace = asyncio.run(demo.run_eval_trace())
    assert len(trace) == 1
    step = trace[0]
    assert step["failures"], "baseline 有失败"
    assert len(step["candidates"]) >= 2, "机械候选 + LLM 候选"
    for c in step["candidates"]:
        assert set(c) >= {"kind", "rules", "scores", "gate_promote", "gate_reason"}
    assert step["promoted"] is not None


def test_make_runtime_explicit_params(monkeypatch):
    monkeypatch.delenv("BAREMETAL_HARNESS_API_KEY", raising=False)
    provider, model, miner = demo.make_runtime(
        api_key="ollama", base_url="http://localhost:11434/v1", model="llama3"
    )
    assert isinstance(provider, demo.OpenAICompatibleClient)
    assert model == "llama3"
    assert miner is provider


def test_run_eval_trace_forwards_runtime_kwargs(monkeypatch):
    captured = {}

    def fake_runtime(api_key=None, base_url=None, model=None):
        captured["api_key"] = api_key
        captured["base_url"] = base_url
        captured["model"] = model
        return demo._offline_provider(), "scripted", demo._offline_miner()

    monkeypatch.setattr(demo, "make_runtime", fake_runtime)
    asyncio.run(demo.run_eval_trace(api_key="k", base_url="u", model="m"))
    assert captured == {"api_key": "k", "base_url": "u", "model": "m"}


def test_run_self_improve_forwards_runtime_kwargs(monkeypatch):
    captured = {}

    def fake_runtime(api_key=None, base_url=None, model=None):
        captured["api_key"] = api_key
        return demo._offline_provider(), "scripted", demo._offline_miner()

    monkeypatch.setattr(demo, "make_runtime", fake_runtime)
    asyncio.run(demo.run_self_improve(api_key="k"))
    assert captured["api_key"] == "k"
