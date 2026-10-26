"""baremetal-harness 评测迭代闭环 demo（Streamlit）。

无 BAREMETAL_HARNESS_API_KEY 走 ScriptedModel 离线回放（仅 6*7 演示）；
配 key 真调 OpenAI 兼容端点（DeepSeek / 本地 Ollama）。
"""
import asyncio
import os

import streamlit as st

import demo

st.set_page_config(page_title="baremetal-harness", page_icon="🔬", layout="wide")

st.title("baremetal-harness")
st.caption("可嵌入的评测迭代 Agent harness · 让 Agent 从失败里自己长出规则")

st.markdown(
    "**Σ-RSI**（scaffold 级递归自改进）——改的是**脚手架**（规则 + 评测套件），不是模型权重。"
    "和 θ-RSI（权重训练）的关键区别：不动模型、可离线复现、每一步可审计。"
)

badge1, badge2, badge3, badge4 = st.columns(4)
with badge1:
    st.markdown("🧪 **机械 verifier**  \n判对错，无 LLM-judge")
with badge2:
    st.markdown("🛡️ **preserve-and-extend**  \n新规则不回退已过任务")
with badge3:
    st.markdown("📏 **标尺不改**  \neval cases 不进搜索空间")
with badge4:
    st.markdown("🎯 **反 Goodhart**  \ncap_points 限评测点数量")

with st.expander("Σ-RSI 循环怎么转（propose → evaluate → weighted_gate → promote）"):
    st.markdown(
        "1. **propose** 候选枚举：从失败 reason 机械突变（粒度 1/2/3）+ 可选 LLM 挖规则。\n"
        "2. **evaluate** 离线评测：注入候选规则，逐任务跑 `run_task`，机械 verifier 判分。\n"
        "3. **weighted_gate** 选最优：preserve-and-extend——无任务分数回退 + 至少一个提升。\n"
        "4. **promote** 原子写回：胜出规则写入 `harness-rules/SKILL.md`，下轮回注。"
    )
    st.caption(
        "demo 实跑：上面四步 + gate。harness 内置未展开：多维 eval points / "
        "heuristic_weights 权重自适应 / cap_points 反 Goodhart。"
    )

st.divider()

with st.expander("🔑 接自己的 key（可选，任意 OpenAI 兼容端点）"):
    ui_key = st.text_input(
        "API Key",
        type="password",
        help="不填走离线回放；本地 Ollama 填 ollama。",
    )
    ui_base = st.text_input(
        "Base URL",
        value="https://api.deepseek.com",
        help="本地 Ollama 填 http://localhost:11434/v1。",
    )
    ui_model = st.text_input("Model", value="deepseek-chat")
    st.caption(
        "安全声明：key 仅存当前浏览器会话内存，不落盘、不写 Streamlit Secrets、"
        "不进 GitHub 仓库。建议用临时 key，用完即删。"
    )

key = ui_key or os.environ.get("BAREMETAL_HARNESS_API_KEY")
if key:
    base = ui_base or os.environ.get("BAREMETAL_HARNESS_BASE_URL") or "https://api.deepseek.com"
    model = ui_model or os.environ.get("BAREMETAL_HARNESS_MODEL") or "deepseek-chat"
    st.info(f"模型：真调 OpenAI 兼容端点 `{base}`（model=`{model}`）")
else:
    st.warning(
        "模型：离线 ScriptedModel 回放（只会答 6/42，仅 6*7 演示有意义）。"
        "跑自己的任务请在上面接 key；本地免费走 Ollama："
        "Base URL `http://localhost:11434/v1` + API Key `ollama`。"
    )

col1, col2 = st.columns(2)
with col1:
    prompt = st.text_input("任务描述", value="What is 6*7? Answer with just the number.")
with col2:
    needle = st.text_input("期望答案（verifier 判输出含此词）", value="42")

tab1, tab2 = st.tabs(["① 评测循环（Σ-RSI 分支搜索）", "② 外层自迭代（run-mine-gate-inject）"])

with tab1:
    st.markdown("propose（候选枚举）→ evaluate（离线评测）→ weighted_gate（preserve-and-extend）→ promote（写回 SKILL.md）。")
    if st.button("跑评测循环（逐中间态）", key="eval", type="primary"):
        tasks = demo.build_tasks(prompt=prompt, needle=needle)
        trace = asyncio.run(
            demo.run_eval_trace(tasks, api_key=ui_key, base_url=ui_base, model=ui_model)
        )
        for i, step in enumerate(trace):
            st.subheader(f"迭代 {i}")
            st.markdown("**baseline 评分**")
            st.json(step["scores"])
            if step["failures"]:
                st.markdown("**失败原因（mine 原料）**")
                for f in step["failures"]:
                    st.write(f"- `{f['task_id']}`：{f['reason']}")
            st.markdown("**候选（逐候选 weighted_gate）**")
            for c in step["candidates"]:
                promoted = c["gate_promote"]
                label = f"{c['kind']} · {'✅ promote' if promoted else '❌ 拒'}"
                with st.expander(label, expanded=promoted):
                    if promoted:
                        st.success(c["gate_reason"])
                    else:
                        st.error(c["gate_reason"])
                    st.write(f"rules = {c['rules']}")
                    st.write(f"scores = {c['scores']}")
            st.markdown("**最终 promote 的规则**")
            if step["promoted"]:
                st.code("\n".join(f"- {r}" for r in step["promoted"]), language="markdown")
                st.caption("将原子写回 harness-rules/SKILL.md（promote_state）")
            else:
                st.write("无 promote（无候选过 gate）")

with tab2:
    st.markdown("四阶段：跑任务 → 挖失败规则（机械 mine_rule）→ preserve-and-extend gate → 注入。")
    if st.button("跑自迭代", key="self", type="primary"):
        tasks = demo.build_tasks(prompt=prompt, needle=needle)
        result = asyncio.run(
            demo.run_self_improve(tasks, api_key=ui_key, base_url=ui_base, model=ui_model)
        )
        st.subheader("baseline vs candidate")
        st.json({"baseline": result["baseline"], "candidate": result["candidate"]})
        st.subheader("挖出的规则")
        st.code(result["rule"])
        st.subheader("gate 决策")
        st.json({"promote": result["promote"], "reason": result["reason"]})

st.divider()
st.caption("源码仓库：[baremetal-harness](https://github.com/v11061373-hue/baremetal-harness)")
