# baremetal-harness demo

[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=v11061373-hue_baremetal-harness-demo&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=v11061373-hue_baremetal-harness-demo)

`baremetal-harness`（[仓库](https://github.com/v11061373-hue/baremetal-harness)）的在线 demo：
可嵌入的评测迭代 Agent harness 的两个核心闭环，离线可跑（无 API Key）；配 key 接 OpenAI 兼容端点跑自定义任务。

## 演示内容

| Tab | 闭环 | 关键 API |
|---|---|---|
| ① 评测循环 | Σ-RSI 分支搜索逐中间态：baseline → 候选枚举（机械+LLM）→ 逐候选 weighted_gate → promote | `propose_candidates` / `evaluate_state` / `score_run` / `weighted_gate` |
| ② 外层自迭代 | run → mine → gate → inject 四阶段 | `run_task` / `failure_traces` / `mine_rule` / `gate` |

机制保证：机械 verifier 判对错（无 LLM-judge）、preserve-and-extend gate 防回退、
eval cases 不进搜索空间（标尺不改）、反 Goodhart `cap_points`。

## 跑自己的任务（可选）

默认离线回放只演示 6*7。跑自己的任务 = 配 OpenAI 兼容端点：

```bash
# DeepSeek
$env:BAREMETAL_HARNESS_API_KEY = "sk-..."
# 本地 Ollama（免费）
$env:BAREMETAL_HARNESS_BASE_URL = "http://localhost:11434/v1"
$env:BAREMETAL_HARNESS_API_KEY = "ollama"
$env:BAREMETAL_HARNESS_MODEL = "qwen2.5"
```

Streamlit Cloud 部署则在 Settings → Secrets 加同名变量。网页输入「任务描述 + 期望答案」即真跑评测闭环。

## 本地跑

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

需 Python 3.12+。

## 测试

```bash
python -m pytest -q
```

## 部署到 Streamlit Cloud

1. push 本仓库到 GitHub。
2. streamlit.io/cloud 用 GitHub 登录，New app 选本仓库，主文件 `streamlit_app.py`。
3. Advanced settings 里 Python 版本选 **3.12**（harness 要求 3.12+）。

---

> 作品集展示文本（叙事、截图、指标）后续另行设计。
