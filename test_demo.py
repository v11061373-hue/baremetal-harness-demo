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
