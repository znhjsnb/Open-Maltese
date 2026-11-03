# Open-Malti 启动入口 (START.md)

欢迎接手 **Open-Malti（马耳他语–中文–英语三语认知词典）** 独立工作区 (`C:\Users\d\Documents\open-malti`)。

## 当前状态（2026-11-03）
- Phase 0.1 / 0.2 本批续作完成：`maltese_sort_key` 在 case 权重后保留冠词存在标记与原始 NFC 文本，保证去冠词后 `ktieb < il-ktieb` 的稳定决胜。
- 新增 `tests/test_maltese_alphabet.py` 与 `tests/test_phase0_inventory_audit.py`。执行 `python -m unittest discover -s tests -v`：58 项通过，0 失败、0 错误。
- 现有两份审计 JSON 逐字节一致；验证 Ġabra 21,083 条记录 / 19,831 个唯一键、Kaikki 80,790 行、精确并集 24,345 / 归一化并集 24,045，以及分类、分区和字母桶守恒。本批未重新生成报告或改动原始数据；候选池规模不等于已批准发布规模。
- 测试口径澄清：`kotba < ktieb < il-ktieb`（O 在 T 前）；精确检索保留 `m'għandix` 撇号，ASCII 容错检索为 `mghandix`；归一化分区以去重后的归一化 Ġabra 词头数为分母。
- 下一步由 Antigravity 按项目分工审查并提交本批文件；用户审阅审计结果后确定词库目标规模，后续阶段继续沿用既定来源与浏览器实测门禁。

## 一、 必读上下文顺序 (Read Order)
1. **[RULES.md](RULES.md)**：项目铁律、Antigravity 与 Codex CLI (`gpt-6.1-sol`) 职责分工矩阵、Emil Kowalski 动效与平铺审美红线。
2. **[docs/PROJECT_HANDOFF.md](docs/PROJECT_HANDOFF.md)**：当前进度、本地已落盘的 `data/raw/` 全量开源语料清单（含字节数校验）以及下一步直接可执行的 **Phase 0 数据对账与词池构建任务**。
3. **[docs/MASTER_PLAN_V2.md](docs/MASTER_PLAN_V2.md)**：经 Codex CLI 严苛审查修订后的 v2.0 完整工程方案（30 字母表确定性排序状态机、八维闪光改良架构、可空多模态字段、四层诚实标签）。
4. **[docs/CODEX_HALLUCINATION_AUDIT.md](docs/CODEX_HALLUCINATION_AUDIT.md)**：前期对话与旧版方案的 8 项事实与设计纠偏存证（特别是 `Dizzjunarju.mt` 仅 81 词的实测结论、Ġabra 词头去重口径、名词阴阳性/集合数与动词双宾语后缀连写规则）。

## 二、 姊妹标杆项目参考 (Sibling Reference Workspaces)
- **工作台与交互母版**：`C:\Users\d\Documents\dict` (`Open-Lexicon 25K`，端口 `8765`)
- **三语八维卡片与混合语源先驱**：`C:\Users\d\Documents\open-melayu` (`Open-Melayu 15K`，端口 `8766`)
