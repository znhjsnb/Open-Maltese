# Open-Malti 启动入口 (START.md)

欢迎接手 **Open-Malti（马耳他语–中文–英语三语认知词典）** 独立工作区 (`C:\Users\d\Documents\open-malti`)。

## 当前状态（2026-11-04 · 23,237 词全量精修大收官 & 开源发布就绪）
- **全库精修 100% 达成**：全库 24,045 个词条中，除了 808 个在底层语料中原本就没有任何英文定义的无证条目保持诚实隔离外，**全部 23,237 个具备实证定义的词条已全部完成三语认知精修**（包含 Tier 1 全部 5,051 词、Tier 2 全部 11,414 词、Tier 3 全部 6,772 词）。
- **完成 24 个全量里程碑**：累计完成 `phase2_milestone_001.json` 至 `phase2_milestone_024.json`（最新 commit `c0d3429`），五道确定性质量门禁 **5/5 通过，0 错误**。
- **展示融合与词性归一化**：上线 `scripts/sense_display.py` 展示融合层，彻底消除跨源重复义项，单义词三语合一，规范小写词性标签（消除 `NOUN / noun` 重影），清除构词框内重复释义。
- **开源发布文档就绪**：已补齐 `LICENSE`（代码 MIT + 数据/文档 CC-BY-SA 4.0 双协议）、`CONTRIBUTING.md` 贡献指南与全新升级的 `README.md`。
- **端口与本地运行**：`http://127.0.0.1:8767/` 实时在线服务，支持 PWA 离线 32 项资产 IndexedDB 存储（SHA-256 校验）。

---

## 前序批次（2026-11-04 · Step 1 展示融合与 Tier 3 队列准备）
- 已按 `.tmp/codex_step1_fusion_and_queue_prep.md` 实施第一步，未启动第二步真实补料。共享 [sense_display.py](scripts/sense_display.py) 生成 `display_senses` / `sense_guide`，维度 03、速跳、抽认卡与 Markdown / 9 列 Anki 均读取同一编号分组。`abaku` 为唯一 `1 · noun` 三语融合义项；`abbanduna` 为 3 条实证义项、无重复总括；`dar` 房屋教学定义仅附名词组，两个动词词根及来源分析保持隔离。原始 teaching 记录兼容保留在证据层，不参与学习者编号。
- POS 展示统一为去重的小写主类；原始来源 POS 不变。02 移除 `.morphology-subentry .sense`，仅在多个不同构词卡标题加入短辨义标签。06/08 仍按原 `analysis.id` 呈现。跨来源融合保留标点并检查词根、性别、集合与词源层冲突；同来源多分析共享 POS/gloss 的全量冲突分组隔离检查通过。
- 原始英文翻译选择器使用稳定 `selector_pos()`，与展示用 `pos_class()` 分离，保留已有 `name` / `propn` 两种绑定。`sense_translations` 支持可选 `en_explanation` / `mt_definition`，展示优先精修英文并保留原文对照；Gate 2 检查展示层重算一致、全部逐义项精修字段及原始扁平义项保护，Gate 4 保留教学材料与搭配的完整验证。
- 全量构建完成；24,045 词的原始 `senses` 与 `lexeme_analyses` 与开工快照逐词摘要相同；19 个 overlay 文件、16,466 词精编数据未变；32 项发布资产字节与 SHA-256 匹配。快速同步的基线只保留来源快照，派生展示字段重算并保持序列化顺序；同步、移除叠加及恢复后的全部发布资产逐字节一致。详见 [完整性证据](tests/artifacts/fusion_integrity.json)。8767 实际返回当前 JS、CSS、manifest，无需重启静态服务，页面需刷新加载新版本。
- 队列新增 `--wave tier3`、`--concurrency`（兼容 `--slots`）与只读 `--dry-run`。实测候选 6,771，缺英文选择器的 808 词明确隔离，清单见 [队列预检](tests/artifacts/fusion_queue_readiness.json)。新 worker 逐义项必须输出中文、马语定义与完整英文解释句；旧 overlay 兼容通过。25 槽并发测试使用隔离假 worker，通过且未调用真实模型。
- 五门 **5/5、0 错误**（[日志](tests/artifacts/fusion_quality_gates.log)）；Node **58 项通过**（[日志](tests/artifacts/fusion_client.log)）；Python 最终串行全量 **133 项通过、0 失败、0 跳过**（[日志](tests/artifacts/fusion_unittest.log)，268.586 秒）。JS 语法与 diff 空白检查通过。测试新增融合、来源边界、英文精修绑定、缺证隔离与 25 槽验证。初轮旧还原断言和并行运行造成的 Node 40 秒超时已修正/排除，保留原有限时，未削减检查。
- 本轮真实 Chrome 门禁未能启动：普通命令在临时服务 `spawn EPERM`；复用 8767 后 Chrome 的 Crashpad/Mojo 通道被 Windows `Access denied (0x5)` 拒绝，页面断言未执行。已更新 PASS 5/9 的构词去重、融合义项与名词绑定断言，不能报告真机通过。见 [浏览器日志](tests/artifacts/fusion_browser_existing_origin.log)。未操作 Git，提交由 Antigravity 宿主负责。
- Antigravity 宿主可直接执行 `$env:OPEN_MALTI_E2E_ORIGIN='http://127.0.0.1:8767'; node tests/frontend.browser.mjs`，完成本批浏览器/视觉及语言学复核后按已批准第二步启动：`python -X utf8 scripts/run_phase2_sliding_queue.py --wave tier3 --concurrency 25 --batch-size 4 --timeout 420 --milestone-interval 100`。详细契约与命令见 [README](README.md)。

## 前序修复批次（2026-11-04 · 空值收敛与 Tier 1+2 覆盖补齐）
- 已保留 01—08 八维平铺，02/06/08 只为有对应实证的子词位生成卡片，空来源合并为紧凑注记。`dar` 名词与动词按 `analysis.id` 隔离；`abaku` 仅保留一张有效构词卡和一张 Kaikki 历史词源卡，无空附着代词小节。
- 构建器统一去重模板及传播链，纳入全库 96 词的 `etymon`；从来源介词表的人称＋数标签归类附着代词，顶层覆盖 55 → 85 词，不把普通动词变位或名词词形归入。`kastellanija` 精编写入现有 `data/enriched/phase2_kastellanija.json`：Tier 1 为 5,051 / Tier 2 为 11,414，合计 16,465 全覆盖，另含 `bongu`，总精编 16,466。
- 已执行 `python -X utf8 scripts/build_phase1_shards.py --apply-phase2-overlays`，32 项资产字节数及 SHA-256 全部匹配；8767 实际返回更新后的 JS、CSS 与 manifest。工程实际发布路径为 `index_lite.json`、`wordforms_lookup.json`、`manifest.json`，未另造任务中所称的索引别名或 overlay 目录。原始数据未修改。
- 五道质量门禁 5/5、0 错误。历史声明检查兼查受保护的 licensed_source 义项，修复“原义项有历史背景但词源正文未提及”的误报；教学编写内容仍不能作为自身证据。`kastellanija` 的旧法院背景与地址另核对了[国家文化遗产清单](https://schmalta.mt/wp-content/uploads/2023/08/DC-01132.pdf)。
- 全库 24,045 词实测 `renderEntry()` HTML 字面 `not recorded`（忽略大小写，不含其他缺失措辞）平均 **15.9518 → 2.5261**，减少 **84.16%**；每次扫描均断言八维仍在。详见 [原始对比](tests/artifacts/blank_fix_render_comparison.json)。
- 最终顺序回归：Python **121 项通过**（[日志](tests/artifacts/blank_fix_unittest.log)），Node **56 项通过**（[日志](tests/artifacts/blank_fix_client.log)），JS 语法与 diff 空白检查通过。宽屏卡片上限已从 1100px 放宽至 1440px，保留移动端规则。本批未操作 Git，提交仍由 Antigravity 宿主负责。
- **本轮真实浏览器门禁未通过启动，页面断言未执行**：要求的 `node tests/frontend.browser.mjs` 首先在临时 Python 服务启动处遇到 `spawn EPERM`；新增可选 `OPEN_MALTI_E2E_ORIGIN` 后复用在线 8767，Chrome 仍因 Crashpad/Mojo 命名通信通道 `Access denied (0x5)` 提前退出（[浏览器日志](tests/artifacts/blank_fix_browser.log)、[Chrome 诊断](tests/artifacts/blank_fix_chrome.log)）。未提高权限或关闭安全机制，不能以历史 PASS 1—12 记录替代本批实测。测试已更新有效卡片 id、空代词小节、词源去重及 1920px 留白断言；宽屏、移动端和离线真机回归仍待 Antigravity 宿主执行。
- Antigravity 宿主直接运行（无需重新构建）：`$env:OPEN_MALTI_E2E_ORIGIN='http://127.0.0.1:8767'; node tests/frontend.browser.mjs`。若使用隔离临时服务，可清除该环境变量后直接运行原命令。成功后再复核语言与听音并提交；当前 `phase2_reviewed` 仍仅表示教学编审，不等于母语独立签核。

| 每词平均字面 `not recorded` | 修复前 | 修复后 |
|---|---:|---:|
| 01 词头发音 | 2.1082 | 0.0000 |
| 02 构词词族 | 8.8633 | 0.3946 |
| 03 三语释义 | 0.0336 | 0.0336 |
| 04 实用搭配 / 05 双境表达 | 0.0000 | 0.0000 |
| 06 屈折附着 | 2.5860 | 0.2131 |
| 07 语用同源 | 1.1012 | 0.9003 |
| 08 历史词源与助记 | 1.2596 | 0.9845 |
| **合计** | **15.9518** | **2.5261** |

## 前序状态（2026-11-04 · Phase 2 16,465 词全量落盘 & Phase 3 工作台移植与 12 项真机 Chrome E2E 门禁全部通过）
- 已按 [Phase 3 共识方案](docs/PHASE3_WORKBENCH_PORT_PLAN.md) 移植双栏工作台：可拖拽并持久保存栏宽、吸顶词头、沉浸阅读、义项速跳、排版浮层与新旧偏好控件同步、3D 抽认卡与下滑关闭、收藏筛选、排序、页码跳转及每批 60 条流式追加。保留原 DOM / 导出契约、8 个顶层维度与 0 个 `<details>`，第二阶段回放按 offset 替换并按 id 去重。音频波形随实际录音或 TTS 播放状态变化，无马语语音时保留指南。
- 02 保留子词位形态与逐义项译释；03 平铺全部来源义项并分开标注原文与教学译释；06/08 按 `analysis.id` 独立呈现屈折和历史词源，不使用顶层聚合字段填补多子词位空缺。`abaku` 的 `abaki / l-abaku` 与意大利语源直出；`dar` 的名词 `djar` 与动词 `jdur / midur` 隔离，屈折节选标注展示数 / 来源总数。
- `prepareOffline` 固定清单版本，依次校验两份索引与 30 分片的 SHA-256，写入 IndexedDB `files` 后回读校验，支持暂停续传；缺存储、回读为空或损坏均拒绝成功。数据库 v2 兼容读取旧 `assets`；`sw.js` 路由和 `/data/` 缓存回退未改。未修改 `data/`，32 项发布资产摘要全部匹配清单。
- 本轮 Python 全量 **117 项通过**（[日志](tests/artifacts/phase3_unittest.log)）；Node 客户端原 37 项及新增检查共 **55 项通过**。覆盖收藏空数组、三种排序、回放幂等、06/08 隔离、离线 32 项保存/暂停/重载、旧缓存迁移、版本固定、写入/回读失败与损坏拒绝、音频播放状态、UTF-8 与选择器契约。JS 语法与 diff 空白检查通过。
- **Antigravity 宿主真机门禁已通过**：已运行 `node tests/frontend.browser.mjs`，**PASS 1–12 全部通过（0 consoleErrors, 0 pageErrors）**，完整验证 06/08 隔离、实际指针拖拽、吸顶/沉浸/义项速跳、偏好双向同步与刷新、3D/下滑关闭、收藏空集、32 项 IndexedDB 字节摘要、断网刷新、减少动态效果及移动端返回词表。

### 前序 Phase 2 双轮对话与滑动队列 / A/B 基准（2026-11-04）
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
