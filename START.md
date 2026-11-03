# Open-Malti 启动入口 (START.md)

欢迎接手 **Open-Malti（马耳他语–中文–英语三语认知词典）** 独立工作区 (`C:\Users\d\Documents\open-malti`)。

## 当前状态（2026-11-03 · Phase 1 审查修复完成）
- 已落实 [Phase 1 审查](docs/CODEX_PHASE1_REVIEW.md) 的 **6 项 P1 与 7 项 P2**，生成版本 `malti-phase1-2026-11-03-r2`。词汇复数排除动词人称/否定/代词连写；`lexeme_analyses` 保留来源记录、词性及词源编号边界；有共时词根但无历史供体证据时保留 `stratum=unspecified`。
- 词池守恒 **24,045**：Tier 1 **5,051** / Tier 2 **11,414** / Tier 3 **7,580**，Tier 1+2 候选池 **16,465**；**30** 个 ASCII 文件名分片。统计与样例见 [lemma_pool_summary.json](data/seed/lemma_pool_summary.json)。
- 反查 **124,488** 个表面形，紧凑表 **4,338,881 字节（4.34 MB）**，1,845 个共享标签描述。Worker 加载轻索引后立即开放基础查词与冠词规则搜索，反查表在第二阶段后台加载。覆盖合法融合/省略冠词，拒绝非法太阳/太阴组合，增音 i 必须命中实存词头。仍有 **10** 行无法连接的来源引用，未补造词头。
- **597** 个词头有真人录音，均有 Commons 文件页署名链接。Ġabra 本地 MDX 标为 **CC BY 3.0**，保留 Camilleri 2013 Appendix D、整理者及 `aħwa` 修正说明；上游现网 CC BY 4.0 与本地快照明确区分。Markdown / Anki（9 列）包含来源许可、审核状态与录音署名链接。
- DMS 数字先于字母、大写先于小写；发音指南最长匹配 `għ / ie`；过期检索报错被 requestId 过滤。全部、Tier 1、Tier 1+2 候选池、样板、词根、罗曼/英语借词和真人发音筛选可用。manifest 版本与 SHA-256 贯穿 Worker、IndexedDB 和分片缓存，SW 支持离线页面及数据回退；离线仅覆盖已完成缓存的索引和已访问分片。
- 已按顺序成功重跑 Phase 0 审计、Phase 1 构建、`python -m unittest discover -s tests -v`：**83 项通过、0 失败、0 跳过**；独立 Node 客户端 **37 项通过**。含逐字节重建、真实 HTTP、同形词/语源/复数回归、基础检索先就绪、离线刷新、错误版本和损坏内容拒绝、存储受限降级。原始数据未改动；两份 Phase 0 审计 JSON 已按修正规则重建。
- 本机工作台入口 **http://127.0.0.1:8767**。复现命令、固定来源 SHA-256、缓存恢复与依赖见 [README.md](README.md)。Phase 1 manifest 记录 78 个实际输入文件的 SHA-256 及 MDX 摘要。
- **待 Antigravity 真机门禁与提交**：本批未执行真实 Chrome、移动端、视觉或听音验收，Node 的隔离客户端/IndexedDB/SW 检查不替代浏览器门禁。25 个原创三语展示词继续标为待语言学复核。按本项目角色与 workspace-write 边界，本轮未操作 Git 提交，保留原有工作区内容。

复现（从本工程根目录运行）：

```powershell
python -X utf8 scripts/phase0_inventory_audit.py
python -X utf8 scripts/build_phase1_shards.py
python -m unittest discover -s tests -v
node tests/phase1_client_checks.mjs
python -X utf8 app/server.py
```

## 一、 必读上下文顺序 (Read Order)
1. **[RULES.md](RULES.md)**：项目铁律、Antigravity 与 Codex CLI (`gpt-6.1-sol`) 职责分工矩阵、Emil Kowalski 动效与平铺审美红线。
2. **[docs/PROJECT_HANDOFF.md](docs/PROJECT_HANDOFF.md)**：当前 Phase 1 交接与本地 `data/raw/` 全量开源语料清单（含字节数校验）；历史 Phase 0 行动指南保留供追溯。
3. **[docs/MASTER_PLAN_V2.md](docs/MASTER_PLAN_V2.md)**：经 Codex CLI 严苛审查修订后的 v2.0 完整工程方案（30 字母表确定性排序状态机、八维闪光改良架构、可空多模态字段、四层诚实标签）。
4. **[docs/CODEX_HALLUCINATION_AUDIT.md](docs/CODEX_HALLUCINATION_AUDIT.md)**：前期对话与旧版方案的 8 项事实与设计纠偏存证（特别是 `Dizzjunarju.mt` 仅 81 词的实测结论、Ġabra 词头去重口径、名词阴阳性/集合数与动词双宾语后缀连写规则）。

## 二、 姊妹标杆项目参考 (Sibling Reference Workspaces)
- **工作台与交互母版**：`C:\Users\d\Documents\dict` (`Open-Lexicon 25K`，端口 `8765`)
- **三语八维卡片与混合语源先驱**：`C:\Users\d\Documents\open-melayu` (`Open-Melayu 15K`，端口 `8766`)
