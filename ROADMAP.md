# 项目路线图（短期）与执行建议

本文档汇总当前可执行的短期路线图与建议，聚焦把最小可用版打磨到可演示、可扩展的状态。

## 一周路线图（状态）

- 稳定化（今天–明天）
  - [x] 报告空列表显示“暂无”（assumptions/risks 防空 bullet）
  - [x] 强制中文输出：默认 `language: zh-CN` 并在提示词中注入语言指令（已在 llm.py 处理）
  - [x] 红线对齐校验：LLM 返回的 `redlines[]` 仅允许当前规则 ID；越界即清洗/警告
  - [x] 文档一致性：README（中/英）统一“LLM-only”与 `config/model.local.yaml` 示例

- 数据集巩固（第2–3天）
  - [x] triage 草稿自动生成与定稿：已由 `triage.draft.jsonl` 产出并合并为 `triage.jsonl`（43 行），人工终审完成（3 处微调已应用）
  - [x] 质量抽检：已生成 20% 抽样集 `review_samples.jsonl`，与 triage 内容一致性良好
  - [x] 数据卡补充：已在数据集仓库 `DATA_CARD.md` 中完善来源/许可/规则版本与分布统计（含占比），新增 Known Limitations；提供 `scripts/update_data_card.py` 一键刷新
  - 参考：数据集仓库 https://github.com/Galaxy-0/idea-crucible-datasets ，发布说明 `RELEASE_NOTES_v0.1.md`

- 评估质量提升（第3–4天）
  - [x] 提示词与结构保障：更强 JSON 约束、越界 redline 提示重试（限 1 次）；加入“引用规则 ID 与理由映射”的明确格式（`reasons_map` 可选）
  - [x] 决策置信度规范：统一 0–1 范围并保留两位小数；不合规值自动归一化
  - [x] 失败兜底：401/403/429 区分与退避重试、响应体记录（本地可诊断）；对 429 使用指数退避+抖动

- 体验与 CLI（第4–5天）
  - [x] 短命令落地：安装后可直接运行 `intake/evaluate/report`（见 README，需 `uv sync` 或 `pip install -e .`）
  - [x] 批量工具：新增 `scripts/batch_evaluate.py`（批量评估 + 统计：决策分布、红线 Top-1/Top-3 命中率，输出 `reports/_stats.json`）

- CI 最小化（第5–6天）
  - [x] 仅跑：schema 校验、类型检查、格式检查（跳过需要密钥的测试）
  - [x] 规则变更守护：所有 PR/Push 均执行 `tests/rules_schema.py`（Pydantic 校验规则与示例 Idea）

- 演示与发布（第7天）
  - [x] 准备 1–2 个端到端示例（idea→verdict→报告），中/英各一
    - 样例：`ideas/demo-idea.yaml`、`ideas/一句话-想法.yaml`
    - 一键生成：`uv run python scripts/gen_examples.py`
    - 产物：`reports/demo-idea.{verdict.json,md}`、`reports/一句话-想法.{verdict.json,md}`
    - 文档：README（中/英）已新增“端到端示例/End-to-End Demo”段落与命令
  - [x] 数据集 v0.1 冻结：`ideas/`、`verdicts/`、`triage.jsonl`、`DATA_CARD.md` 完整
    - 路径：`/Users/galaxy/Project/Startup/idea-crucible-datasets`
    - 一致性：`triage.jsonl` 43 条，`verdicts/` 43 个，均能在 `ideas/` 中找到对应条目
    - 数据卡：`DATA_CARD.md` 含来源/许可/规则版本/分布统计/时间戳
    - 已完成提交与标签：`git commit -m "Freeze dataset v0.1"`，`git tag v0.1`

## 本周交付物

- 代码层：红线对齐校验、报告空值修复、LLM 错误分型/退避、中文固定
- 数据层：RFS 38 条 + HN 精选若干的 triage 终稿与统计报表（分布、样例）
- 文档层：多语言 README 统一、DATA_CARD.md 完善、最小使用手册（含批量命令）

## 今日进展与下一步

- 已完成
  - 报告空 bullet 修复（agent/main.py）
  - 红线 ID 对齐（agent/engine.py）
  - 文档示例统一（README.zh-CN.md / README.en.md）
  - 模板说明更新为 LLM 驱动（templates/report.md）
  - 端到端示例脚本与文档：`scripts/gen_examples.py`，README 中/英增加示例段落
  - 数据集同步辅助脚本：`scripts/sync_verdicts.py`
  - 数据集 v0.1 冻结核查+提交+打标签（本地 tag：v0.1）

- 下一步（明日优先）
  - （可选）推送数据集标签到远端：`git push origin v0.1`
  - （可选）为演示生成静态页或导出 PDF（基于 `reports/*.md`）
  - （可选）数据集一键流水线：整合“批量评估 + 同步判定 + 刷新数据卡”到单脚本

## 长期方向（可选）

- 规则集版本化：`rules/core` 增加 `version:` 与变更日志；verdict 写入 `rules_version`
- 评测指标：决策一致率、红线 Top-1/3 命中、理由可读性（人工评）
- 可插拔模型：`model.yaml` 支持多模型候选与失败回退（优先 JSON 合规的轻模型）
- 半自动扩写：对 idea 的 `user/scenario/triggers/alts` 进行 LLM 批量扩写至派生目录，保留原件

## 使用速记（本地）

- 录入想法：`uv run -m agent.cli intake "一句话想法"`
- 评估想法：`uv run -m agent.main evaluate --idea ideas/<slug>.yaml --model-cfg config/model.local.yaml`
- 生成报告：`uv run -m agent.main report --idea ideas/<slug>.yaml`
- 数据集批量评估（示例）：
  - 对 `idea-crucible-datasets/ideas/rfs-*.yaml` 批量跑，复制 `reports/*.verdict.json` 至数据集 `verdicts/`（当前已全量评估 38/38）
  - 一键生成演示：`uv run python scripts/gen_examples.py`
  - 同步判定至数据集：`uv run python scripts/sync_verdicts.py --dst ../idea-crucible-datasets/verdicts`

---

说明：本路线图与建议对应当前“LLM-only + 红线规则校验”的实现现状，目标是一周内形成可演示、可协作的 v0.1。后续可根据真实评测数据与人工复核反馈，滚动更新本文件。
