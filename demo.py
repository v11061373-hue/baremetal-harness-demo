"""baremetal-harness demo 核心：评测迭代闭环 + 外层自迭代。

公开面：
- run_eval_trace()    Σ-RSI 分支搜索逐中间态：baseline→候选枚举→逐候选 gate→promote
- run_eval_loop()     汇总版：branch_search 一步 + 写回 SKILL.md
- run_self_improve()  外层自迭代四阶段：run→mine→gate→inject（干跑报告）

模型：无 BAREMETAL_HARNESS_API_KEY 走 ScriptedModel 离线回放（仅 6*7 有意义）；
有 key 走 OpenAICompatibleClient 真调（DeepSeek 默认 / 任意 OpenAI 兼容端点如本地 Ollama）。
"""
import os
import tempfile
from pathlib import Path

from baremetal_harness.agent.limits import RunLimits
from baremetal_harness.core.messages import ResponseCompleted, TextDelta
from baremetal_harness.meta import (
    EvolutionTask,
    ScaffoldState,
    branch_search,
    evaluate_state,
    failure_traces,
    gate,
    mine_rule,
    mine_rule_llm,
    promote_state,
    propose_candidates,
    run_task,
    score_run,
    weighted_gate,
)
from baremetal_harness.model.openai_compat import OpenAICompatibleClient
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

_DEFAULT_PROMPT = "What is 6*7? Answer with just the number."
_DEFAULT_NEEDLE = "42"


def build_tasks(
    prompt: str = _DEFAULT_PROMPT, needle: str = _DEFAULT_NEEDLE
) -> tuple[EvolutionTask, ...]:
    return (EvolutionTask("math", prompt, CheckContains(needle)),)


def _offline_provider() -> ScriptedModel:
    # 离线回放 fail→pass：baseline 2 次失败耗尽，候选各 1 次通过。
    return ScriptedModel((
        (TextDelta("6"), ResponseCompleted("stop")),
        (TextDelta("6"), ResponseCompleted("stop")),
        (TextDelta("42"), ResponseCompleted("stop")),
        (TextDelta("42"), ResponseCompleted("stop")),
    ))


def _offline_miner() -> ScriptedModel:
    return ScriptedModel(((TextDelta("answer 42"), ResponseCompleted("stop")),))


def make_runtime(
    api_key: str | None = None, base_url: str | None = None, model: str | None = None
) -> tuple[object, str, object]:
    """(provider, model, miner)。有 key 真调 OpenAI 兼容端点；无 key ScriptedModel 回放。"""
    api_key = api_key or os.environ.get("BAREMETAL_HARNESS_API_KEY")
    if api_key:
        base_url = base_url or os.environ.get("BAREMETAL_HARNESS_BASE_URL") or "https://api.deepseek.com"
        model = model or os.environ.get("BAREMETAL_HARNESS_MODEL") or "deepseek-chat"
        provider = OpenAICompatibleClient(base_url, api_key)
        return provider, model, provider
    return _offline_provider(), "scripted", _offline_miner()


async def run_eval_trace(
    tasks: tuple[EvolutionTask, ...] | None = None, *, iterations: int = 1,
    api_key: str | None = None, base_url: str | None = None, model: str | None = None,
) -> list[dict]:
    """Σ-RSI 分支搜索逐中间态：baseline 分/失败 → 候选枚举 → 逐候选 gate → promote。

    复刻 branch_search 内循环，但把 propose_candidates / evaluate_state / score_run /
    weighted_gate / mine_rule_llm 的每步结果暴露出来，供算法侧可视化。
    """
    tasks = tasks or build_tasks()
    provider, model, miner = make_runtime(api_key=api_key, base_url=base_url, model=model)
    current = ScaffoldState()
    trace: list[dict] = []
    for _ in range(iterations):
        runs = await evaluate_state(
            current, tasks, provider=provider, model=model, tools=None,
            workspace=None, limits=_LIMITS,
        )
        scores = {
            t.task_id: score_run(t, r.result).score
            for t, r in zip(tasks, runs, strict=True)
        }
        failures = failure_traces(tuple(r for r in runs if not r.passed))
        candidates: list[dict] = [
            {"kind": "mech", "rules": list(c.rules), "state": c}
            for c in propose_candidates(current, failures)
        ]
        if miner is not None:
            llm_rule = await mine_rule_llm(miner, failures)
            if llm_rule:
                state = ScaffoldState((*current.rules, llm_rule))
                candidates.append({"kind": "llm", "rules": list(state.rules), "state": state})
        evaluated: list[dict] = []
        best: ScaffoldState | None = None
        best_scores = scores
        for cand in candidates:
            cruns = await evaluate_state(
                cand["state"], tasks, provider=provider, model=model,
                tools=None, workspace=None, limits=_LIMITS,
            )
            cscores = {
                t.task_id: score_run(t, r.result).score
                for t, r in zip(tasks, cruns, strict=True)
            }
            decision = weighted_gate(scores, cscores)
            evaluated.append({
                "kind": cand["kind"],
                "rules": cand["rules"],
                "scores": cscores,
                "gate_promote": decision.promote,
                "gate_reason": decision.reason,
            })
            if decision.promote and sum(cscores.values()) > sum(best_scores.values()):
                best, best_scores = cand["state"], cscores
        trace.append({
            "scores": scores,
            "failures": [{"task_id": f.task_id, "reason": f.reason} for f in failures],
            "candidates": evaluated,
            "promoted": list(best.rules) if best else None,
        })
        if best is None:
            break
        current = best
    return trace


async def run_eval_loop(
    tasks: tuple[EvolutionTask, ...] | None = None, *,
    api_key: str | None = None, base_url: str | None = None, model: str | None = None,
) -> dict:
    """Σ-RSI 分支搜索一步（汇总版）：候选枚举→离线评测→weighted_gate→写回 SKILL.md。"""
    tasks = tasks or build_tasks()
    provider, model, miner = make_runtime(api_key=api_key, base_url=base_url, model=model)
    steps = await branch_search(
        tasks,
        provider=provider,
        miner_client=miner,
        model=model,
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


async def run_self_improve(
    tasks: tuple[EvolutionTask, ...] | None = None, *,
    api_key: str | None = None, base_url: str | None = None, model: str | None = None,
) -> dict:
    """外层自迭代四阶段：run→mine→gate（干跑报告，不落盘）。"""
    tasks = tasks or build_tasks()
    provider, model, _ = make_runtime(api_key=api_key, base_url=base_url, model=model)

    async def _run_all(prov):
        return {
            t.task_id: await run_task(
                t, provider=prov, model=model, tools=None,
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
