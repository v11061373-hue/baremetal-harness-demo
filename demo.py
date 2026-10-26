"""baremetal-harness demo 核心：评测迭代闭环 + 外层自迭代，全离线（无 API Key）。

两个公开面：
- run_eval_loop()     Σ-RSI 分支搜索：score→propose→evaluate→weighted_gate→写 SKILL.md
- run_self_improve()  外层自迭代四阶段：run→mine→gate→inject（干跑报告）
"""
import tempfile
from pathlib import Path

from baremetal_harness.agent.limits import RunLimits
from baremetal_harness.core.messages import ResponseCompleted, TextDelta
from baremetal_harness.meta import (
    EvolutionTask,
    branch_search,
    failure_traces,
    gate,
    mine_rule,
    promote_state,
    run_task,
)
from baremetal_harness.model.scripted import ScriptedModel


class CheckContains:
    """机械 Verifier：输出含 needle 即通过，否则返回失败原因。"""

    def __init__(self, needle: str) -> None:
        self._needle = needle

    async def verify(self, output: str, prompt: str) -> str | None:
        if self._needle in output:
            return None
        return f"output missing {self._needle!r}"


_LIMITS = RunLimits(2, 2)


def build_tasks() -> tuple[EvolutionTask, ...]:
    return (
        EvolutionTask(
            "math", "What is 6*7? Answer with just the number.", CheckContains("42")
        ),
    )


def _offline_provider() -> ScriptedModel:
    # 离线回放 fail→pass：baseline 2 次失败耗尽，候选各 1 次通过。
    return ScriptedModel((
        (TextDelta("6"), ResponseCompleted("stop")),
        (TextDelta("6"), ResponseCompleted("stop")),
        (TextDelta("42"), ResponseCompleted("stop")),
        (TextDelta("42"), ResponseCompleted("stop")),
    ))


async def run_eval_loop(tasks: tuple[EvolutionTask, ...] | None = None) -> dict:
    """Σ-RSI 分支搜索一步：候选枚举→离线评测→weighted_gate→选最优写回 SKILL.md。"""
    tasks = tasks or build_tasks()
    miner = ScriptedModel(((TextDelta("answer 42"), ResponseCompleted("stop")),))
    steps = await branch_search(
        tasks,
        provider=_offline_provider(),
        miner_client=miner,
        model="scripted",
        tools=None,
        workspace=None,
        limits=_LIMITS,
        iterations=1,
    )
    rendered = [
        {
            "step": i,
            "scores": step.scores,
            "promoted": list(step.promoted.rules) if step.promoted else None,
        }
        for i, step in enumerate(steps)
    ]
    skill_md = None
    final = steps[-1].promoted if steps else None
    if final is not None:
        with tempfile.TemporaryDirectory() as tmp:
            skills = Path(tmp) / "skills"
            promote_state(final, skills_dir=skills)
            skill_md = (
                skills / "harness-rules" / "SKILL.md"
            ).read_text(encoding="utf-8").rstrip()
    return {"steps": rendered, "skill_md": skill_md}


async def run_self_improve(tasks: tuple[EvolutionTask, ...] | None = None) -> dict:
    """外层自迭代四阶段：run→mine→gate（干跑报告，不落盘）。"""
    tasks = tasks or build_tasks()
    provider = _offline_provider()

    async def _run_all(prov):
        return {
            t.task_id: await run_task(
                t, provider=prov, model="scripted", tools=None,
                workspace=None, limits=_LIMITS,
            )
            for t in tasks
        }

    baseline = await _run_all(provider)
    failures = failure_traces(tuple(r for r in baseline.values() if not r.passed))
    rule = mine_rule(None, failures)
    candidate = await _run_all(provider)
    decision = gate(
        {t: r.passed for t, r in baseline.items()},
        {t: r.passed for t, r in candidate.items()},
    )
    return {
        "baseline": {t: r.passed for t, r in baseline.items()},
        "failures": [{"task_id": f.task_id, "reason": f.reason} for f in failures],
        "rule": rule,
        "candidate": {t: r.passed for t, r in candidate.items()},
        "promote": decision.promote,
        "reason": decision.reason,
    }
