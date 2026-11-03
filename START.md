# Open-Malti 启动入口 (START.md)

欢迎接手 **Open-Malti（马耳他语–中文–英语三语认知词典）** 独立工作区 (`C:\Users\d\Documents\open-malti`)。

## 当前状态（2026-11-04 · 双轮对话与滑动队列 / A/B 基准已实现，宿主实测待完成）
- 本轮将首批 100 词全部补齐两轮 `colloquial.messages`（姓名与中文角色、口语、标准表达、中文、英文），保留原有三语整段对话；已有规范表达的标准栏与口语相同。`validate_overlay` / Gate 4 共用反稀释校验：每个实证义项中文非空、两个不同三语搭配、至少两轮完整对话、助记至少八字符。前端逐轮平铺并转义所有文本，PASS 8 消除了清空输入与筛选的 debounce 竞态，并等待卡片加载及 provenance。
- 新增 [滑动队列](scripts/run_phase2_sliding_queue.py) 与 [80 词 A/B 基准](scripts/run_phase2_ab_benchmark.py)。只读 worker 使用 `gpt-6.1-sol / high`、UTF-8 stdin 与精确 POS/英文选择器；单词独立五门验证、部分成功落盘、两词 360 秒重试、耗尽重试后隔离。队列支持要求的全部 CLI 参数；A/B 为 10×4/420 秒对 5×8/840 秒，15 批并发，报告含重试、首轮质量和 B 的批内前后位置比较。完整 Wave 1 为 5,384，当前未精编 5,286；完整 Tier 1+2 为 16,465。偶奇交错不保证分类分布完全相同，报告记录实际差异，token 数明确标为估算。
- 已执行快速同步：30 分片与索引/manifest 更新，`phase2_baseline.json` 保持叠加前来源记录，精编仍为 100。五门 5/5、0 错误；Python 全量 **117 项通过**（`tests/artifacts/phase2_queue_unittest_final.log`），Node 客户端 **37 项通过**。隔离测试覆盖部分提交、重复/缺失输出、精确义项、超时、重试隔离、持续补位及 A/B 统计；未启动嵌套 Codex 或 Chrome。
- **Antigravity 宿主下一步**：执行 `node tests/frontend.browser.mjs` 与 `python -X utf8 scripts/run_phase2_ab_benchmark.py`，再复核语言、移动端及听音。真实基准输出将写入 `data/enriched/phase2_tier1_batch2_ab.json` 与 `data/audit/phase2_ab_benchmark_report.json`；本轮未生成虚构实测报告，未操作 Git。使用方式见 README。

### 前序 100 词基线（2026-11-03，后续状态以上述更新为准）
- 用户已批准 **Phase 2 受控批次精编**，UI 布局重构推迟至 Phase 2 之后。本批完成 [phase2_tier1_batch1.json](data/enriched/phase2_tier1_batch1.json)：原 25 词升级＋75 个新增 Tier 1 核心词，共 **100 词**、**200 组搭配**、**200 段双境教学场景**、**413 个逐 POS/原英文义项绑定的中文译释**。原展示词 `bongu`（Tier 3）、`għand`（Tier 2）保留原分层，其余 98 词均为 Tier 1。
- 来源词池继续守恒 **24,045**：Tier 1 **5,051** / Tier 2 **11,414** / Tier 3 **7,580**；已丰富 **100**＋未丰富 **23,945**。反查表面形 **124,488**，真人录音词头 **597**，均有 Commons 文件页链接。原始数据与既有来源校验和不变。
- 新增确定性冠词引擎与 [五门校验器](scripts/phase2_quality_gates.py)：Unicode/损坏文本、形态/同形词诚实、冠词/实证代词、许可/教学归属、守恒/分层样本。当前 [五门报告](data/audit/phase2_quality_gate_report.json) **5/5 通过、0 错误**；报告明确程序不能认证地道性或取代母语与听音验收。
- 所有 `data/enriched/*.json` 按文件名排序加载，重键/未知词头/来源字段改写/未译原义项会拒绝。完整构建与 [快速同步器](scripts/sync_enriched_to_shards.py) 共用叠加、版本、序列化逻辑；分片摘要和来源基线校验后才同步，移除叠加可恢复基础记录。`skola → skejjel` 在基础构建标为 `hybrid_assimilated`，不补造词根。发布数据规范化了 12,738 处来源格式控制字符串，并隔离标明 15 处损坏文本；原始文件不变，计数见 summary。
- `dar` 等同形词按原来源记录/词性分开呈现中文；来源英文保留，译释附 `translation_provenance=authored_pedagogical`。教学义项、搭配、场景与助记标为 `phase2_reviewed`（本批编审，不代表独立母语专家签核）。样板筛选从 manifest 动态读取 **100**，多子词位条目也显示助记。冠词校验与检索均拒绝 `l-iktieb / l-iżmien / l-itriq / ij-jum`。
- 验证：完整构建成功；Python 全量回归 **107 项通过、0 失败、0 跳过**（日志 `tests/artifacts/phase2_unittest_final.log`），Node 客户端 **37 项通过**；全构建对照与快速同步/移除/恢复逐字节一致。本地 HTTP 资源与隔离临时端口测试通过。JS 语法及 diff 空白检查通过。
- **真实浏览器未通过启动门禁**：已运行 `node tests/frontend.browser.mjs`，在创建子进程时因 `spawn EPERM` 退出；浏览器连接宿主不可用，现有 Chrome 的计算机操作访问亦未获批准。脚本已加入 `dar` 中文隔离、助记及动态 100 词筛选断言，但本轮不能把它们报为真机通过。母语语言学、移动端、视觉与听音验收仍待 Antigravity 完成。
- 按 workspace-write 与工程分工，本轮不操作 `.git` 或提交。下一步由 Antigravity 在允许创建 Chrome 子进程的宿主运行浏览器脚本与语言学抽检，再审查并提交。详细命令与边界见 [README](README.md)。

复现（从本工程根目录运行）：

```powershell
python -X utf8 scripts/phase0_inventory_audit.py
python -X utf8 scripts/build_phase1_shards.py
python -X utf8 scripts/phase2_quality_gates.py
python -X utf8 -m unittest discover -s tests -v
node tests/phase1_client_checks.mjs
node tests/frontend.browser.mjs
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
