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
  - 短命令落地：提供安装后的 `intake/evaluate/report` 可执行（`pip install -e .` 或 `uv sync` 后生效）
  - 批量工具：数据集批量评估/统计脚本（决策分布、红线 Top-1/Top-3 命中率）

- CI 最小化（第5–6天）
  - 仅跑：schema 校验、类型检查、格式检查（跳过需要密钥的测试）
  - 规则变更守护：新增/修改规则时自动做 Pydantic 校验

- 演示与发布（第7天）
  - 准备 1–2 个端到端示例（idea→verdict→报告），中/英各一
  - 数据集 v0.1 冻结：`ideas/`、`verdicts/`、`triage.jsonl`、`DATA_CARD.md` 完整

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

- 下一步（明日优先）
  - 发布对外演示用的端到端示例（idea→verdict→report），中/英各 1（使用数据集中的代表样本）
  - 为数据集新增一键脚本（可选）：批量评估 + 刷新数据卡 + 生成抽样报告

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

---

说明：本路线图与建议对应当前“LLM-only + 红线规则校验”的实现现状，目标是一周内形成可演示、可协作的 v0.1。后续可根据真实评测数据与人工复核反馈，滚动更新本文件。
