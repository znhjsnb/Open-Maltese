# Codex CLI 独立对立面架构与框架审查报告 (`CODEX_PHASE1_REVIEW.md`)

> **审查模型**：`OpenAI Codex v0.159.2` (`gpt-6.1-sol / high`, `-s read-only`)  
> **审查时间**：2026-11-03  
> **审查范围**：`docs/MASTER_PLAN_V2.md`、`/grill-me` 四项架构决策、`scripts/maltese_alphabet.py`、`scripts/phase0_inventory_audit.py`、`scripts/build_phase1_shards.py`、`scripts/phase1_showcase.py`、`app/server.py`、`app/static/*` 及全套单元测试。  
> **审查总结论**：**Request changes（存在 6 项 P1 语言学/工程边界缺陷与 7 项 P2 稳健性缺口，需全部修复并通过回归测试后方可锁定 Phase 1）**。无 P0 级崩溃或注入漏洞。

---

## 一、 实测基线数据核对

| 指标项 | 实测值 | 审计说明 |
| :--- | ---: | :--- |
| **归一化独立词头数** | **24,045** | 精确大小写词头为 24,345 |
| **Tier 1（双源黄金核心词）** | **5,051** | Ġabra 与 Kaikki 双方均作为独立词位收录 |
| **Tier 2（单源高完整度候选词）** | **11,414** | Kaikki 独有词位 + Ġabra 带词根与音标词位 |
| **Tier 3（Ġabra 基础实证词）** | **7,580** | 保留基础词性、释义与已有音标/词根，扩展维度置空 |
| **变位反查表面词形键数** | **124,488** | 源自 69,617 行 Kaikki 纯屈折记录及词形表 |
| **具备真人录音 URL 的独立词头** | **597** | 源自 Kaikki 中 720 条带音频记录（部分同词多词性合并后为 597 词头） |

---

## 二、 P1 级必改问题（6 项）

### P1-1：动词人称复数变位被误归入名词性「词汇复数 (`plural_forms`)」
- **定位**：`scripts/phase0_inventory_audit.py:407` 与 `scripts/build_phase1_shards.py:265`
- **复现**：直接按 `tags` 中含 `'plural'` 提取 `plural_forms`，导致动词 `kiteb`（写）的复数人称变位 `iktbu, jiktbu, jiktbux, ktibna` 以及拟动词 `għand` 的复数代词连写被当成“名词复数”展示。
- **修复要求**：仅对名词/形容词/分词词条提取非人称变位的词汇复数（排除含 `first-person`, `second-person`, `third-person`, `imperfect`, `perfect`, `imperative`, `negative`, `possessive` 等变位标签的项）；新增回归测试确保 `ktieb → kotba` 保留，而 `kiteb` 的 `plural_forms` 不含 `jiktbu` 等动词变位。

### P1-2：同形异义词（Homographs）合并时跨词性/跨词源串味
- **定位**：`scripts/build_phase1_shards.py:202`
- **复现**：以 **`dar`** 为例，阴性名词 `dar`（房子，复数 `djar`）与动词 `dar`（转动，未完成体 `jdur`，过去分词 `midur`，词根 `d-w-r`）因拼写相同被压扁进同一组标量字段，导致名词义与动词变位、双词根混杂。
- **修复要求**：左栏列表保持单一同形词入口，但词条详情内部必须保留按 `(source, pos, etymology_number)` 隔离的 **`lexeme_analyses`（子词位分析数组）**，使各自的词性、阴阳性、词根、单复数/变位表与词源互不污染。

### P1-3：将共时词根（Synchronic Root）直接等同于历时闪米特词源（Historical Stratum）
- **定位**：`scripts/phase0_inventory_audit.py:378` 与 `scripts/build_phase1_shards.py:220`
- **复现**：7,095 个仅在 Ġabra 中有辅音词根但无历史词源文本的词被直接标为 `stratum = 'semitic'`。而马耳他语中部分早期西西里/意大利借词也已同化出共时词根模板。
- **修复要求**：严格区分“共时词根存在性（`has_root` / `root_consonants`）”与“历时词源层（`stratum`）”；无明确词源模板或词源文本证明其源自阿拉伯语时，`stratum` 必须保持 `'unspecified'`（或单独标注 `synchronic_root_only`），绝不将共时词根直接冒充为历时词源考据。

### P1-4：定冠词与融合介词剥离规则既漏判合法同化形、又误放行非法组合
- **定位**：`app/static/worker.js:35` 与 `scripts/maltese_alphabet.py:62`
- **复现**：
  1. 漏判合法融合介词+太阳字母同化：`fix-xemx` (`fi + ix-xemx`)、`bid-dar` (`bi + id-dar`)、`lill-kelb` (`lil + il-kelb`)、`x-xemx`、`d-dar` 未能反查回原形；
  2. 误判非法冠词组合：`ix-ktieb`（太阳冠词 `ix-` 配太阴辅音 `k`）被错误剥离为 `ktieb` 并显示“已剥离定冠词”。
- **修复要求**：在 Python 与前端 Worker 中统一实现带音系合法性校验的冠词/融合介词剥离器：
  - 太阳字母冠词（`iċ-, id-, in-, ir-, is-, it-, ix-, iż-, iz-`、省略元音形 `ċ-, d-, ...` 及融合介词 `fiċ-/fid-/fin-/fir-/fis-/fit-/fix-/fiż-/fiz-`, `biċ-/bid-/...`, `maċ-/mad-/...`, `taċ-/tad-/...`, `għaċ-/għad-/...`, `liċ-/lid-/...`）**仅当词干首字素确实等于该太阳辅音时才合法**（从而支持 `fix-xemx → xemx`、`bid-dar → dar` 并拒绝 `ix-ktieb`）；
  - `il- / fil- / bil- / mal- / tal- / għall- / lil- / lill-` 仅当词干不以太阳辅音开头时合法；
  - 增音 `l-i...` / `fl-i...` 仅对特定词首辅音群（如 `s/x/ż/z + 辅音` 的 `l-iskola → skola`）且命中实存词头时生效，并在提示条中明确区分“词库实证变位”与“语法规则剥离”。

### P1-5：Ġabra 快照许可证标注偏差（CC BY 3.0 vs 4.0）与 Wikimedia 音频署名直链缺失
- **定位**：`scripts/build_phase1_shards.py:32`、`README.md` 与页脚
- **复现**：本地 `Gabra.mdx` 头部及 `gabra-maltese-dictionary/docs/ATTRIBUTION.md` 明确记录该快照遵循 **CC BY 3.0**（Camilleri 2013 Appendix D），而前端与 README 写成了 `CC BY 4.0`；同时音频仅保留了文件名，缺少可点击的 Wikimedia Commons 文件页链接（`https://commons.wikimedia.org/wiki/File:...`），且 Anki/Markdown 导出遗漏了来源与待审状态说明。
- **修复要求**：全库统一修正 Ġabra 快照许可证为 **CC BY 3.0（上游现网标 CC BY 4.0，本地打包快照按原包声明保留 CC BY 3.0 及 `aħwa` 修正说明）**；为每条录音生成完整的 `audio_commons_url` 并在卡片与导出内容中附上来源与审核状态标签。

### P1-6：Web Worker 冷启动同步阻塞加载 23.9 MB 冗余反查表
- **定位**：`app/static/worker.js:84` 与 `scripts/build_phase1_shards.py`
- **复现**：Worker 在启用基础查词前同步拉取并解析 `index_lite.json` (7.85 MB) + `wordforms_lookup.json` (23.91 MB)，且反查表中重复存储了十余万次长字符串标签，导致冷启动内存额外增加约 140 MiB。
- **修复要求**：
  1. **结构紧凑化**：将 `wordforms_lookup.json` 改为紧凑字典 + 标签枚举表（`tag_table` + `[lemma, tag_id]`），将体积从 ~23.9 MB 压缩至 ~4–5 MB；
  2. **两阶段非阻塞加载**：Worker 加载完 `index_lite.json` 后**立即开放 24,045 词头秒搜与定冠词规则反查**，后台异步加载紧凑版 `wordforms_lookup.json` 并更新状态徽章。

---

## 三、 P2 级稳健性与规范对齐问题（7 项）

1. **DMS 200:2009 次级排序方向对齐 (`maltese_alphabet.py:116`)**：按 DMS 200:2009 §4.1–4.2，数字排在字母之前（`0..9 < A..Z`），且同字母仅大小写不同时大写排在小写之前（`Marsa < marsa`）。修正 `maltese_sort_key` 及对应测试。
2. **数据集版本一致性校验 (`worker.js` / `db.js`)**：将 `manifest.json` 的版本号与 SHA-256 传入 Worker，确保 `index_lite.json`、`wordforms_lookup.json` 与 30 个分片绑定同一版本代际。
3. **发音拆解弹窗双字母 `għ` 误触发 `ħ` (`app.js:122`)**：改用最长前缀字素切分（优先识别 `għ` 与 `ie`），避免 `għajn` 同时弹出 `għ` 和 `ħ` 两条提示。
4. **过期 Worker 报错未校验 `requestId` (`app.js:190`)**：对 Worker 异常响应同样校验 `requestId`，防止旧请求报错覆盖新搜索结果。
5. **补齐筛选胶囊与诚实命名 (`app.js:39`)**：补齐 `精选样板 (25)`、`有闪米特词根`、`有真人发音` 筛选器，并将 `Tier 1+2 精编池` 诚实命名为 `Tier 1+2 候选池 (16.5K)`。
6. **Service Worker 与 IndexedDB 离线闭环 (`sw.js` / `db.js`)**：将 `manifest.json`、`index_lite.json` 与 `wordforms_lookup.json` 纳入 IndexedDB/SW 缓存策略，确保断网刷新后仍可查词。
7. **更新 `START.md` 与 `README.md` 复现指引**：同步 Phase 1 最新实测统计、数据源固定校验和与恢复命令。
