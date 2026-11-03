# Open-Malti 项目交接与 Phase 0 启动手册 (PROJECT_HANDOFF.md)

> **更新时间**：2026-11-03  
> **当前工作区**：`C:\Users\d\Documents\open-malti`  
> **前序会话来源**：由 `Open-Lexicon 25K` (`C:\Users\d\Documents\dict`) 会话完成 `/grill-me` 需求对齐、Codex CLI 幻觉审计、Master Plan v2.0 敲定及 Phase 0 开源原始数据包拉取后拆出独立窗口。

---

## 一、 核心架构共识与防幻觉铁律（必读摘要）

在启动任何脚本或精编任务前，必须牢记以下经 **Codex CLI (`gpt-6.1-sol`) 实测核查** 的关键事实（详见 [docs/CODEX_HALLUCINATION_AUDIT.md](CODEX_HALLUCINATION_AUDIT.md) 与 [docs/MASTER_PLAN_V2.md](MASTER_PLAN_V2.md)）：

1. **`Dizzjunarju.mt` 真实规模为 81 词（非爬虫漏抓）**：
   - 经直接拉取 `https://dizzjunarju.mt/lista.html`（`21,685` bytes）与 `assets/site.js`（`29,681` bytes）拆解验证，该站是由 `build_static_site.py` 生成的纯静态展示站，全站 `<a class='lista-entry'>` 仅 **81 个词条**，30 个字母中有 11 个字母为空（`<span class='lista-jump-empty'>`）。
   - **定位**：仅作新词形、现代借词与学术规范的**辅助参考源**，严禁将其当作万词级底座。
2. **核心词典底座（`data/raw/` 已拉取就绪）**：
   - **Ġabra 开源词库快照 (CC-BY 4.0)**：已拉取 `data/raw/gabra-maltese-dictionary` 仓库及 Release 包 `data/raw/GabraMalteseDict_MDX_v1.0.zip`（含 `19,831` 唯一词头 / `21,083` 词条记录，涵盖 `lexemes` 词根、词性、派生动词 Form I–X 与屈折词形）+ 官方 `data/raw/gabra-api` Schema 仓库。
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
