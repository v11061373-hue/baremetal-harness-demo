"""baremetal-harness 评测迭代闭环 demo（Streamlit）。

无 BAREMETAL_HARNESS_API_KEY 走 ScriptedModel 离线回放（仅 6*7 演示）；
配 key 真调 OpenAI 兼容端点（DeepSeek / 本地 Ollama）。
"""
import asyncio
import os

import streamlit as st

import demo

st.set_page_config(page_title="baremetal-harness demo", page_icon="🔬", layout="wide")
st.title("baremetal-harness：评测迭代闭环")
st.caption(
    "可嵌入的评测迭代 Agent harness —— Σ-RSI 分支搜索 + agent 外层自迭代。"
    "机械 verifier 判对错，无 LLM-judge；preserve-and-extend gate 防回退。"
)

key = os.environ.get("BAREMETAL_HARNESS_API_KEY")
if key:
    base = os.environ.get("BAREMETAL_HARNESS_BASE_URL") or "https://api.deepseek.com"
    model = os.environ.get("BAREMETAL_HARNESS_MODEL") or "deepseek-chat"
    st.info(f"模型：真调 OpenAI 兼容端点 `{base}`（model=`{model}`）")
else:
    st.warning(
        "模型：离线 ScriptedModel 回放（只会答 6/42，仅 6*7 演示有意义）。"
        "跑自己的任务请配 `BAREMETAL_HARNESS_API_KEY`（Streamlit Secrets）；"
        "本地免费走 Ollama：`BAREMETAL_HARNESS_BASE_URL=http://localhost:11434/v1`"
        "+ `BAREMETAL_HARNESS_API_KEY=ollama`。"
    )

col1, col2 = st.columns(2)
with col1:
    prompt = st.text_input("任务描述", value="What is 6*7? Answer with just the number.")
with col2:
    needle = st.text_input("期望答案（verifier 判输出含此词）", value="42")

tab1, tab2 = st.tabs(["① 评测循环（Σ-RSI 分支搜索）", "② 外层自迭代（run-mine-gate-inject）"])

with tab1:
    st.markdown("Σ-RSI：propose（候选枚举）→ evaluate（离线评测）→ weighted_gate（preserve-and-extend）→ promote（写回 SKILL.md）。")
    if st.button("跑评测循环（逐中间态）", key="eval"):
        tasks = demo.build_tasks(prompt=prompt, needle=needle)
        trace = asyncio.run(demo.run_eval_trace(tasks))
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
                verdict = "✅ promote" if c["gate_promote"] else "❌ 拒"
                st.markdown(f"- `{c['kind']}` {verdict}：{c['gate_reason']}")
                st.write(f"　rules={c['rules']}，scores={c['scores']}")
            st.markdown("**最终 promote 的规则**")
            if step["promoted"]:
                st.code("\n".join(f"- {r}" for r in step["promoted"]), language="markdown")
                st.caption("将原子写回 harness-rules/SKILL.md（promote_state）")
            else:
                st.write("无 promote（无候选过 gate）")

with tab2:
    st.markdown("四阶段：跑任务 → 挖失败规则（机械 mine_rule）→ preserve-and-extend gate → 注入。")
    if st.button("跑自迭代", key="self"):
        tasks = demo.build_tasks(prompt=prompt, needle=needle)
        result = asyncio.run(demo.run_self_improve(tasks))
        st.subheader("baseline vs candidate")
        st.json({"baseline": result["baseline"], "candidate": result["candidate"]})
        st.subheader("挖出的规则")
        st.code(result["rule"])
        st.subheader("gate 决策")
        st.json({"promote": result["promote"], "reason": result["reason"]})

st.divider()
st.caption("源码仓库：[baremetal-harness](https://github.com/v11061373-hue/baremetal-harness)")
