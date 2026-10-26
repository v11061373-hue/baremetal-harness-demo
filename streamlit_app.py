"""baremetal-harness 评测迭代闭环 demo（Streamlit）。全离线，无 API Key。"""
import asyncio

import streamlit as st

import demo

st.set_page_config(page_title="baremetal-harness demo", page_icon="🔬", layout="wide")
st.title("baremetal-harness：评测迭代闭环")
st.caption(
    "可嵌入的评测迭代 Agent harness —— Σ-RSI 分支搜索 + agent 外层自迭代。"
    "本 demo 全离线可跑（ScriptedModel 回放 fail→pass，无 API Key）。"
)

tab1, tab2 = st.tabs(["① 评测循环（Σ-RSI 分支搜索）", "② 外层自迭代（run-mine-gate-inject）"])

with tab1:
    st.markdown("任务：`What is 6*7?`，机械 verifier 判「输出含 `42`」。回放 baseline 答错 → 候选答对。")
    if st.button("跑评测循环", key="eval"):
        result = asyncio.run(demo.run_eval_loop())
        st.subheader("每步评分与 promote 规则")
        st.json(result["steps"])
        st.subheader("写回的 SKILL.md")
        st.code(result["skill_md"], language="markdown")

with tab2:
    st.markdown(
        "四阶段：跑任务 → 挖失败规则（机械 mine_rule）→ preserve-and-extend gate → 注入。"
    )
    if st.button("跑自迭代", key="self"):
        result = asyncio.run(demo.run_self_improve())
        st.subheader("baseline vs candidate")
        st.json({"baseline": result["baseline"], "candidate": result["candidate"]})
        st.subheader("挖出的规则")
        st.code(result["rule"])
        st.subheader("gate 决策")
        st.json({"promote": result["promote"], "reason": result["reason"]})

st.divider()
st.caption("源码仓库：[baremetal-harness](https://github.com/v11061373-hue/baremetal-harness)")
