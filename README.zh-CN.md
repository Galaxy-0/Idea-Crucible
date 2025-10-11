# Idea-Crucible（先证伪评估框架）

面向初创想法的“红线优先、先证伪”工作流最小可用实现，聚焦快速识别不可行方向，并给出可迭代的下一步。

## 交付物
- 代码脚手架（配置、数据模型、CLI）
- 种子红线规则（10 条）与规则文件
- 一页报告模板与示例输出

## 目录与组件
- `agent/` 核心与命令行
  - `agent/main.py` — 命令：`intake` | `evaluate` | `report`
  - `agent/schemas.py` — 数据模型：`Rule`, `Idea`, `Evidence`, `Verdict`
  - `agent/engine.py` — 规则匹配与仲裁（MVP）
- `config/`
- （已移除）`config/modes.yaml`、`config/weights.yaml`
  - `config/rules/core/*.yaml` — 红线规则（按类别）
- `ideas/` — 示例想法（YAML）
- `reports/` — 评估结果与报告
- `templates/report.md` — 一页报告模板（先证伪）

## 数据模型（简要）
- Rule：`id`, `scope`, `condition`(文本/表达式), `severity`, `rationale`, `sources[]`, `owner`, `version`, `sunset`, `decision`(deny|caution|continue), `keywords[]`, `next_steps[]`
- Idea：`intent`, `user`, `scenario`, `triggers`, `alts`, `assumptions[]`, `risks[]`
- Evidence：`type`(primary|secondary|tertiary), `provenance`, `weight`, `sample_size`, `excerpts[]`, `timestamp`
- Verdict：`decision`(deny|caution|go), `reasons[]`, `conf_level`, `redlines[]`, `next_steps[]`

## 红线规则（V1，10 条）
1) 技术/物理上不可行，或在可预见周期内依赖未被证明的前置科学 → deny
2) 单位成本下界 > 客户价值上界（18–36 月无可信路径）→ deny
3) 核心数据在法律/平台上不可得，且无合规替代 → deny
4) 监管硬阻或取证/许可周期 > 跑道，且无分阶段路径 → deny
5) 单一平台依赖且存在“关停”风险，无缓解 → caution/deny
6) 前 1000 名目标用户在结构上无法触达（不是“贵”，是“不可达”）→ deny
7) 双边网络效应、但单边不具备独立价值 → deny
8) 目标市场内缺乏可行护城河（数据/流程嵌入/网络/规模）→ caution
9) 伦理/安全红旗（系统性伤害、滥用向量）且不可缓解 → deny
10) 验证周期 > 跑道，且无可递增价值关卡（无 RAT 路径）→ deny

每条规则包含：条件、严重级别、动机、来源；触发时输出“deny/caution/continue”，`caution` 附带下一步实验。

## 流程（MVP）
- intake：从简短描述生成规范化 Idea（YAML）
- evaluate：加载规则并匹配，合成决策与置信度
- report：渲染一页报告（含理由与下一步）

## 快速开始（评估依赖大模型）
- 环境：Python 3.10+
- 安装 uv：参考 https://docs.astral.sh/uv/
- 创建虚拟环境：`uv venv`（或 `uv venv -p 3.11`）
- 安装核心依赖：`uv sync`（默认仅安装核心依赖）
- 安装依赖：`uv sync`
- 环境变量：
  - 复制 `.env.example` 为 `.env` 并填写：
    - `LLM_API_URL`（如 https://api.openai.com/v1）
    - `LLM_API_KEY`（你的 API Key）
  - 或直接在 shell 中设置 `OPENAI_API_KEY`
- 运行：`uv run python -m agent.main ...`

命令示例
- 录入（intake）：
  `uv run python -m agent.main intake --desc "需要未验证 AGI 的双边市场" --out ideas/demo-idea.yaml`
- 评估（LLM）：
  `uv run python -m agent.main evaluate --idea ideas/demo-idea.yaml --mode llm-only --model-cfg config/model.yaml`
- 报告（report）：
  `uv run python -m agent.main report --idea ideas/demo-idea.yaml`

## 关键文件
- `config/rules/core/`：10 条红线（YAML）
- `templates/report.md`：一页报告模板
- `ideas/demo-idea.yaml`：示例输入

## 大模型集成
- 模型配置：`config/model.yaml`（默认 provider=openai，model=gpt-4o-mini，密钥环境变量 `OPENAI_API_KEY`）。
- 评估模式：`llm-only`（默认）
- 提示：客户端直接构造 JSON 输出约束的提示

## 使用 uv（推荐）
- `uv sync` 安装依赖；设置 `.env` 或 `OPENAI_API_KEY` 后直接评估。



## 评测基准（Agent 分诊）
目的：验证 Agent 对“是否值得继续（go/caution/deny）”的判断与红线提示是否有参考性，支持回归与比较不同版本/模式。

数据与格式：
- 位置：`benchmarks/triage/pilot.jsonl`（每行一个样本）
- 字段：`id`, `idea_path`, `gold_decision` ∈ {deny,caution,go}, 可选 `gold_redlines[]`, `notes`
- Schema：`benchmarks/triage/schema.json`

运行评测（离线 rules 模式）：
- `./.venv/bin/python -m agent.main benchmark --data benchmarks/triage/pilot.jsonl --mode rules`
- 输出：`reports/benchmarks/<slug>/summary.json` 与 `details.jsonl`

指标与建议门槛：
- 决策准确率 Accuracy：≥ 0.70（MVP），目标 ≥ 0.80
- 关键类别召回（deny）：≥ 0.90（避免漏报高危）
- 红线覆盖 Jaccard（宏平均）：≥ 0.60（MVP）
- 置信度校准：开启 LLM 模式后补充 Brier/ECE（规则模式仅作参考）
- 理由/下一步：抽样人工复核 10–20%

注：当前中文样本可能因关键词匹配触发过度/不足，属已知限制。可逐步扩充中文关键词或引入更鲁棒的匹配策略。
