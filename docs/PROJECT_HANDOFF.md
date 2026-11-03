# Open-Malti 项目交接与 Phase 0 启动手册 (PROJECT_HANDOFF.md)

> **更新时间**：2026-11-03  
> **当前工作区**：`C:\Users\d\Documents\open-malti`  
> **前序会话来源**：由 `Open-Lexicon 25K` (`C:\Users\d\Documents\dict`) 会话完成 `/grill-me` 需求对齐、Codex CLI 幻觉审计、Master Plan v2.0 敲定及 Phase 0 开源原始数据包拉取后拆出独立窗口。

---

## Phase 2 当前交接（2026-11-03）

2026-11-04 更新：首批 100 词已全部升级双轮 `messages` 并同步，反稀释门与前端渲染、PASS 8 竞态修复完成；新增只读 worker 滑动队列与 80 词 A/B 基准。Python 117 项、Node 37 项、五门 5/5 通过。未启动嵌套 Codex / Chrome，未运行真实 A/B；Antigravity 在宿主直接执行 `node tests/frontend.browser.mjs` 和 `python -X utf8 scripts/run_phase2_ab_benchmark.py`。详细最新状态与命令以 START / README 为准。

最新状态以 [START](../START.md) 为准。已完成 100 词叠加、确定性五门校验与快速同步；词池 24,045、丰富 100、未丰富 23,945，原 25 词保留，其中 `bongu`/`għand` 的 Tier 3/2 分层不变。教学内容均有原创来源标签，413 个源义项中文译释逐 POS/英文绑定，`dar` 名词与动词不混用。UI 布局重构推迟至 Phase 2 后。

本轮完整构建、Python 回归、37 项 Node 客户端及逐字节同步检查通过；详细最终结果见 START。五道确定性门全通过，但真实 Chrome 命令因 `spawn EPERM` 未能启动，计算机操作访问 Chrome 亦未获批准；不把机器门禁等同母语语言学、听音与浏览器验收。Antigravity 在宿主跑 `node tests/frontend.browser.mjs`（现有 8 组验收），复核 100 词的地道性、移动端及听音后再提交。原始数据、Phase 0 报告不变，当前 worker 不操作 Git。

后续修改 `data/enriched/*.json` 后运行 `python -X utf8 scripts/run_phase2_enrichment.py --sync`。`--validate-only` 仅验证并写确定性报告；`--batch-size 25` 准备后续 Tier 1 来源材料，只有显式 `--dispatch` 才调用单个本机 Codex CLI worker；本轮未调用额外 worker 或付费 API。完整使用与缓存基线恢复见 README。

---

## Phase 1 当前交接（2026-11-03）

用户已确认三层全词池、30 桶导航（IE 在 I 内）、清洁词头与词形追踪条、诚实三分支发音。实现与操作说明见 [README](../README.md)，最新短状态见 [START](../START.md)，实测统计见 [lemma_pool_summary.json](../data/seed/lemma_pool_summary.json)。本段取代下文历史行动指南中的“等待词库定容”状态；历史原始资料清单保留。

- 构建器 `scripts/build_phase1_shards.py` 生成 24,045 个词头、30 片及两个检索索引；Tier 1/2/3 实测为 5,051 / 11,414 / 7,580。Tier 2 的 Ġabra-only 资格使用同一条记录的有效实证词根 + IPA + 英文释义，计 6,898；Kaikki-only 4,516。估算规模已按来源复算替换。
- 反查表 124,488 个表面形；10 行无法连接既有词池的引用已列在 summary。冠词与 `m'għandix` 等明确例外标为 `grammar_reference`，其余引用沿原有形态表连接。音频 720 是原始行数；独立规范化词位覆盖为 597。
- 审查的 6 项 P1 / 7 项 P2 已修复，版本 `malti-phase1-2026-11-03-r2`：子词位按来源/POS/词源编号隔离，共时词根与历史语源分开，词汇复数排除人称变位；合法冠词规则、DMS 次序、最长字素发音指南、过期报错过滤与全部筛选完成。Ġabra MDX 标 CC BY 3.0，录音均有 Commons 文件页链接，两类导出保留来源及待审标签。
- 反查表紧凑为 4,338,881 字节，第一阶段基础查词不等待反查表；manifest 版本与摘要传至 Worker，IndexedDB 缓存清单、索引与已访问分片，SW 缓存页面模块和数据。固定输入校验和、完整复现及恢复方式见 README；离线缓存缺失时明确保留功能边界。
- 25 个展示词具有原创三语释义、搭配、书面例句与日常对话，并标为待语言学复核；其它未丰富字段保持空值。没有自动填补词根、十型、词频排名或马耳他语单语释义。
- 验证：构建成功，unittest 全量 83 项通过；另有 Node 客户端 37 项通过；跨进程重建逐字节一致；隔离临时端口的实际 HTTP 资源与边界测试通过；JavaScript 语法检查通过。8767 当前未运行，按 README 启动即可。TTS 检测脚本保留，先前检测未发现本机 eSpeak-NG / System.Speech 马语 voice；本批未重测听音。
- Antigravity 下一步直接读取本段与现有代码，完成真实 Chrome E2E、视觉/移动端检查及听音；重点复核词形追踪、I→ie、语音缺失弹窗、四主题与复制按钮。本次整改未执行真机浏览器；Node 隔离环境中的 IndexedDB/SW 离线回归不代替该门禁。
- 通过浏览器与语言学抽检后，由 Antigravity 按项目分工审查并执行 Git 原子提交。`app/static/data/` 与测试临时产物已忽略，代码、测试、README 与 seed summary 保持可跟踪；原始数据未改动，Phase 0 两份报告已按修正规则重建；保留用户已有 `docs/codex_phase1_prompt.md`。

---

## 一、 核心架构共识与防幻觉铁律（必读摘要）

在启动任何脚本或精编任务前，必须牢记以下经 **Codex CLI (`gpt-6.1-sol`) 实测核查** 的关键事实（详见 [docs/CODEX_HALLUCINATION_AUDIT.md](CODEX_HALLUCINATION_AUDIT.md) 与 [docs/MASTER_PLAN_V2.md](MASTER_PLAN_V2.md)）：

1. **`Dizzjunarju.mt` 真实规模为 81 词（非爬虫漏抓）**：
   - 经直接拉取 `https://dizzjunarju.mt/lista.html`（`21,685` bytes）与 `assets/site.js`（`29,681` bytes）拆解验证，该站是由 `build_static_site.py` 生成的纯静态展示站，全站 `<a class='lista-entry'>` 仅 **81 个词条**，30 个字母中有 11 个字母为空（`<span class='lista-jump-empty'>`）。
   - **定位**：仅作新词形、现代借词与学术规范的**辅助参考源**，严禁将其当作万词级底座。
2. **核心词典底座（`data/raw/` 已拉取就绪）**：
   - **Ġabra 开源词库快照（本地 MDX CC BY 3.0；上游现网 CC BY 4.0）**：已拉取 `data/raw/gabra-maltese-dictionary` 仓库及 Release 包 `data/raw/GabraMalteseDict_MDX_v1.0.zip`（含 `19,831` 唯一词头 / `21,083` 词条记录，MDX 保留词根、词性、英文释义及已有 IPA，未导出动词十型与屈折词形表）+ 官方 `data/raw/gabra-api` Schema 仓库。
   - **Kaikki / English Wiktionary 马耳他语全量转储**：`data/raw/kaikki.org-dictionary-Maltese.jsonl`（`99,021,210` bytes，约 94.4 MB，含词头、词性、英语释义、词源、IPA 及屈折表）。
   - **Camilleri 动词屈折黄金表**：`data/raw/maltese-verb-inflections/`（186 个核心动词全套变位 TSV）。
   - **WikiPron 宽式 IPA 音标库**：`data/raw/mlt_latn_broad.tsv`（`543,365` bytes）与 `mlt_latn_broad_filtered.tsv`（`541,408` bytes）+ G2P 学术规则论文 `data/raw/maltese-g2p-rules.pdf`。
   - **MUDT (Universal Dependencies v2.15) 真实句法树库**：`data/raw/mt_mudt-ud-{train,dev,test}.conllu`（共约 2.0 MB 真实标注语料）+ Tatoeba 句对 `data/raw/mlt_sentences.tsv.bz2` + 玛尔塔大学语音语料元数据 `data/raw/MASRI/`。
3. **动态诚实定容（严禁硬凑数字）**：
   - 严禁在未跑完去重对账前拍脑袋锁死“15,000 词”；必须先运行 Phase 0 交叉核验脚本，产出《马耳他语词头覆盖率与多源对账报告 (`data/audit/lexeme_inventory_report.json`)》后，按实际有效独立 Lemma 核定首批精编规模（如 Top 3,000 / 5,000 / 10,000）。
4. **马耳他语专属语言学建模（区别于马来语）**：
   - **30 字母表确定性排序与分片**：`A, B, Ċ, D, E, F, Ġ, G, GĦ, H, Ħ, I, IE, J, K, L, M, N, O, P, Q, R, S, T, U, V, W, X, Ż, Z`（含双字母单音素 `GĦ`, `IE` 最长前缀匹配分词器）。
   - **双轨构词模型（Dimension 02）**：
     - 闪米特词条：`三/四辅音词根 (Għerq, 如 k-t-b) + 格型 (Mudell, 如 kiteb / ktieb / miktub) + 动词派生第 I–X 式`；
     - 罗曼/西西里/英语借词：**严禁伪造辅音词根**，必须走 `借词源词 + 马耳他语形态同化后缀 (-a / -azzjoni / -ar 等)` 轨道；
     - 名词/形容词专项字段：阴阳性 (`m./f.`)、集合名词 (`kollettiv`)、单数个体名词 (`singulattiv`)、破碎复数 (`plural miksur`) 与规则复数 (`plural sħiħ`)；
     - 动词专项字段：完成时 (`perfett`)、未完成时 (`imperfett`)、命令式 (`imperattiv`) 及高频直接/间接宾语人称代词后缀连写（如 `kitibhieli` = `kiteb + hie + li`）。
   - **双轨语境与冠词连音（Dimension 05 & 06）**：
     - 替换马来语的 `Bahasa Pasar`，改为 **定冠词 `il-` 太阳字母同化 (`iċ-, id-, in-, ir-, is-, it-, ix-, iż-, iz-`) + 介词融合 (`fil-, bil-, mal-, għall-, tal-, lil-`) + 马英双语切换 (`Maltenglish Code-Switching`)**；
     - 所有扩展维度（`dual_scenarios`, `sandhi_and_clitics`, `cultural_pragmatics`, `etymology`）在 JSON Schema 中均为 **Nullable（可空）**，无真实语料支撑时宁缺毋滥。

---

## 二、 本地已就绪原始数据包清单 (`data/raw/`)

| 路径 | 大小 / 类型 | 用途与许可 |
| :--- | :--- | :--- |
| `data/raw/kaikki.org-dictionary-Maltese.jsonl` | `99,021,210` bytes (~94.4 MB) | Kaikki Wiktionary 马耳他语全量 JSONL 转储（词头、词性、英语释义、词源、屈折表） |
| `data/raw/gabra-maltese-dictionary/` | Git Repo | Jingyuan Zheng 整理的 Ġabra 2026 快照仓库（含构建脚本与 MDX 源说明） |
| `data/raw/GabraMalteseDict_MDX_v1.0.zip` | `898,857` bytes | Ġabra 2026 离线词库发布包（`19,831` 词头 / `21,083` 词条，CC-BY 4.0） |
| `data/raw/gabra-api/` | Git Repo | 玛尔塔大学 MLRS 官方 `gabra-api` 源码与数据模型定义 |
| `data/raw/maltese-verb-inflections/` | Git Repo | John J. Camilleri 186 个核心动词完整变位表 TSV（CC-BY-SA 3.0） |
| `data/raw/mlt_latn_broad.tsv` | `543,365` bytes | WikiPron 马耳他语宽式 IPA 词表 |
| `data/raw/mlt_latn_broad_filtered.tsv` | `541,408` bytes | WikiPron 过滤版马耳他语 IPA 词表 |
| `data/raw/maltese-g2p-rules.pdf` | `500,556` bytes | 马耳他语正字法转 IPA (G2P) 规则论文（含词尾清化、省音与 `għ/h` 音长规则） |
| `data/raw/mt_mudt-ud-train.conllu` | `1,046,177` bytes | Universal Dependencies 马耳他语树库训练集 |
| `data/raw/mt_mudt-ud-dev.conllu` | `466,063` bytes | Universal Dependencies 马耳他语树库开发集 |
| `data/raw/mt_mudt-ud-test.conllu` | `501,555` bytes | Universal Dependencies 马耳他语树库测试集 |
| `data/raw/mlt_sentences.tsv.bz2` | `8,183` bytes | Tatoeba 马耳他语句库压缩包 |
| `data/raw/MASRI/` | Git Repo | 玛尔塔大学语音实验室 MASRI 语料库工具与元数据 |

> **注**：马耳他国家语言委员会 (`kunsilltalmalti.gov.mt`) 的 3 份正字法 PDF 链接开启了浏览器质询保护（裸 `curl` 会返回 `4,540` bytes 的挑战页，已清理），后续如需调阅可通过浏览器下载：
> - `https://kunsilltalmalti.gov.mt/file.aspx?f=112` (*Deċiżjonijiet 1*, 2008)
> - `https://kunsilltalmalti.gov.mt/file.aspx?f=262` (*Tagħrif fuq il-Kitba Maltija II*, 2018)
> - `https://kunsilltalmalti.gov.mt/file.aspx?f=280` (*Aġġornament tal-Ortografija*, 2021)

---

## 三、 新窗口接手后的第一步行动指南 (Immediate Action Plan)

1. **Phase 0.1 — 拆包与全量词头去重对账 (`scripts/phase0_inventory_audit.py`)**：
   - 解压/解析 `data/raw/GabraMalteseDict_MDX_v1.0.zip` 与 `data/raw/kaikki.org-dictionary-Maltese.jsonl`；
   - 交叉比对 `maltese-verb-inflections`、`mlt_latn_broad.tsv` 与 `mt_mudt-ud-*.conllu` 词频；
   - 严格区分 **独立词位 (Lemma)** 与 **屈折变体 (Wordform)**，输出 `data/audit/lexeme_inventory_report.json`（含闪米特词根覆盖率、借词占比、IPA 覆盖率、30 字母分片分布）。
2. **Phase 0.2 — 30 字母排序与分词引擎 + 单元测试 (`scripts/maltese_alphabet.py` & `tests/test_maltese_alphabet.py`)**：
   - 实现 [docs/MASTER_PLAN_V2.md](MASTER_PLAN_V2.md) 第 3.2 节定义的 30 字母最长前缀匹配分词器（`għ`, `ie`, `ċ`, `ġ`, `ħ`, `ż`）与容错去音符双索引归一化函数，交由 Codex CLI 编写严苛边界测试。
3. **Phase 1 — 复刻 `Open-Lexicon 25K` 浏览台外壳并扩展 30 字母双行网格**：
   - 直接以 `C:\Users\d\Documents\dict\app\static\{index.html,styles.css,app.js,worker.js,db.js}` 为母版，将字母栏扩展为 31 键（`全部` + 30 个马耳他语字母，2 行 × 16 列），接入马耳他语八维卡片渲染器。
