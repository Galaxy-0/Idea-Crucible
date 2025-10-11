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
  - `config/modes.yaml` — 模式：consulting | hybrid | logic-only
  - `config/weights.yaml` — 严重级别权重与阈值
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

## 快速开始
- 环境：Python 3.10+
- 安装依赖：`pip install -r requirements.txt`

命令示例
- 录入（intake）：
  `python -m agent.main intake --desc "需要未验证 AGI 的双边市场" --out ideas/demo-idea.yaml`
- 评估（规则逻辑）：
  `python -m agent.main evaluate --idea ideas/demo-idea.yaml --mode logic-only`
- 评估（混合：规则+大模型）：
  `python -m agent.main evaluate --idea ideas/demo-idea.yaml --mode hybrid --model-cfg config/model.yaml`
- 评估（仅大模型）：
  `python -m agent.main evaluate --idea ideas/demo-idea.yaml --mode llm-only --model-cfg config/model.yaml`
- 评估（Claude Agent SDK）：
  `python -m agent.main evaluate --idea ideas/demo-idea.yaml --mode agent-claude`
- 报告（report）：
  `python -m agent.main report --idea ideas/demo-idea.yaml`

## 关键文件
- `config/weights.yaml`：严重级别权重与阈值
- `config/modes.yaml`：评估模式预设
- `config/rules/core/`：10 条红线（YAML）
- `templates/report.md`：一页报告模板
- `ideas/demo-idea.yaml`：示例输入
- `reports/sample.md`：示例报告

## 大模型集成
- 模型配置：`config/model.yaml`（默认 provider=openai，model=gpt-4o-mini，密钥环境变量 `OPENAI_API_KEY`）。
- 评估模式：
  - `logic-only`：仅用规则引擎。
  - `hybrid`：与大模型结果保守合并（deny > caution > go）。
  - `llm-only`：完全由大模型输出结构化判定。
- 提示模板参考：`templates/llm_prompt.txt`（实际请求使用 JSON 输出约束）。

## 使用 uv（推荐）
- 安装 uv：参考 https://docs.astral.sh/uv/
- 创建虚拟环境：`uv venv`（或 `uv venv -p 3.11`）
- 安装依赖：`uv sync`（默认仅安装核心依赖，不包含任何外部模型/SDK）
- 运行命令：
  - 录入：`uv run python -m agent.main intake --desc "..." --out ideas/demo-idea.yaml`
  - 评估（规则逻辑，默认）：`uv run python -m agent.main evaluate --idea ideas/demo-idea.yaml --mode logic-only`
  - 报告：`uv run python -m agent.main report --idea ideas/demo-idea.yaml`

## 可选启用 LLM（uv extras）
- OpenAI：`uv sync --extra llm` 后即可使用 `--mode hybrid/llm-only`。
- Claude Agent SDK：`uv sync --extra claude` 后可使用 `--mode agent-claude`（需安装 Node.js 与 `@anthropic-ai/claude-code`）。

## 接入 Claude Agent SDK
- 依赖安装：
  - `pip install claude-agent-sdk`
  - `npm install -g @anthropic-ai/claude-code`（Claude Code 2.0.0+）
  - 安装 Node.js 并确保在 PATH 中
- 运行：`python -m agent.main evaluate --idea ideas/demo-idea.yaml --mode agent-claude`
- SDK 通过 Claude Code 流式交互，最终返回结构化 JSON 判定。
