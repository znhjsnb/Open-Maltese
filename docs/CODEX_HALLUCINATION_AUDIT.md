# Codex CLI 对话幻觉与方案事实独立审计报告（`task-351`）

> **审计执行器**：`OpenAI Codex v0.159.2`（`gpt-6.1-sol / high`，`--search` 联网检索 + 本地只读沙箱）  
> **审计对象**：Antigravity 前序全部马耳他语回复与提问选项（Steps `262`, `317`, `319`, `323`）及 `open_malti_master_plan.md`（v1.0 草案）  
> **审计总结论**：**v1.0 草案不通过（需按下方逐行表修订为 v2.0）**。Antigravity 在 Step 317 宣布“完整核实”后，仍在 Step 319、323 把尚未取得的数据说成现成直链、把部分字段说成完整覆盖，并在 `Dizzjunarju.mt` 的覆盖率、发布主体与抓取边界上前摇后摆；同时，不能为了凑幻觉清单而把真实存在的 `mlt_latn_broad.tsv`、MASRI `text2phon` 与 `inizzja` 误判为伪造。

---

## 第一部分：关键数据源与对话声明独立核查

### 一、 六大核心数据源的真实状态（A–F）

#### A. WikiPron：`mlt_latn_broad.tsv` 真实存在，但非独立于 Wiktionary 的第二信源
- `CUNY-CL/wikipron` 官方 [data/scrape/summary.tsv](https://raw.githubusercontent.com/CUNY-CL/wikipron/refs/heads/master/data/scrape/summary.tsv) 明确列出：
  - `mlt_latn_broad.tsv`：**21,208** 条
  - `mlt_latn_broad_filtered.tsv`：**21,124** 条
- **纠偏要点**：
  1. WikiPron 数据同样抽取自 Wiktionary，**不能算作独立于 Kaikki/Wiktionary 的第二套平行发音证据**；
  2. WikiPron **工具代码**为 Apache 2.0，但 `data/` 下的 Wiktionary 抽取数据受 Wiktionary 许可约束，不能混为一谈。

#### B. MASRI `text2phon` 与 Mark Borg G2P：资源真实存在，但交付形态在 Step 319 被混写
- [UMSpeech/MASRI 官方仓库](https://github.com/UMSpeech/MASRI) 确实说明含规则式 IPA 转写器并给出 `from masri.transcribe.g2p import text2phon` 调用示例（但尚未在本地拉取运行验证）；
- [Mark Borg 公开的 G2P 规则](https://mark-borg.github.io/assets/maltese-g2p-rules.pdf) 是 **8 页 PDF 文档**（含规则顺序、上下文条件与例外说明），**不是即用型 TSV 文件**。
- **Step 319 的幻觉/夸大**：把 Tatoeba TSV、WikiPron TSV、MASRI Python 函数与 Mark Borg PDF 规则笼统合称为“全部是 TSV / GitHub 现成文件直链”。

#### C. Kaikki / Wiktionary Maltese JSONL：含相关模板，但不等于“直接具备统一顶层词根字段”
- [Kaikki Maltese 首页](https://kaikki.org/dictionary/Maltese/index.html) 标示：**79,775 distinct words**，postprocessed JSONL 约 **94.4 MB**（源于 2026-10-01 dump，2026-10-25 抽取）。
- **Step 317/319 的失真**：
  1. 将页面公布的 `79,775 distinct words` 直接改称为“79,775 条记录”，且在 Step 323 无实测依据地声称“混杂了约 6 万条变位词形”；
  2. 词根信息在 Kaikki 中通常嵌在 `etymology_templates`（如 `{"name": "mt-root", "args": {"1": "ħ-b-b"}}`）或分类/词源文本中，而非所有词条都有统一的顶层 `root` 字段——例如实查 [`kiteb` 的 Kaikki JSON](https://kaikki.org/dictionary/Maltese/meaning/k/ki/kiteb.html) 虽有 IPA、词源与 `head_templates`，但**并无直接可读的顶层 `root` 字段**，且页面带有抽取错误记录。

#### D. Ġabra 与 Camilleri 仓库：把“API 源码仓库 + 小型测试集 + 第三方快照”混成了整库直链
- [`MLRS/gabra-api`](https://github.com/MLRS/gabra-api) 是 **API 源码仓库**（其 README 指向外部 BSON dump 下载入口，而该上游下载入口当前重定向至马耳他大学首页）；克隆 `MLRS/gabra-*` 源码仓库**不等于**拿到了完整词典数据库。
- [`johnjcamilleri/maltese-verb-inflections`](https://github.com/johnjcamilleri/maltese-verb-inflections) 是**少量动词的人工检查变位测试集**（README 注明部分文件为空），**绝不能冒充覆盖约两万词头的词根与十型总表**。
- [Ġabra 官方前端声明 (`i18n.yaml`)](https://raw.githubusercontent.com/MLRS/gabra-web/master/src/assets/data/i18n.yaml) 明确指出：它不是完整马耳他语词典，信息详略不一，存在词、词形与义项缺失，且大量屈折词形为自动生成、可能含错。

#### E. MLRS Korpus Malti v4.0 与 UD_Maltese-MUDT：省略了词形还原（Lemmatization）与消歧工序
- [Korpus Malti v4.0 论文](https://aclanthology.org/2022.deeplo-1.10.pdf) 报告 **466,601,373 tokens、20,758,071 句**，但 [HuggingFace `MLRS/korpus_malti` 数据卡](https://huggingface.co/datasets/MLRS/korpus_malti) 明确写明：默认数据**仅有句子文本，没有 lemma 或其他形态标注**。
- [UD_Maltese-MUDT 官方说明](https://universaldependencies.org/treebanks/mt_mudt/index.html)（2,074 句、44,162 tokens，CC BY-SA 4.0）同样明确标示：**`Lemmas: not available`、`Features: not available`**。
- **Step 317 的过度承诺**：声称从 Korpus Malti 可直接提取“按词元（Lemma）聚合的真实词频排名”，省略了分词、附着成分剥离、词形还原与同形异义消歧等核心工程环节，且 CC BY-NC-SA 4.0 的许可与数据库权利边界需严格核查，不能自行宣布“提取统计词频天然豁免”。

#### F. `Dizzjunarju.mt`（国家在线词典）：项目真实，但发布主体、排他性、可见规模与抓取合规性被严重拔高
- **核查事实**（依据 [马耳他大学启动公告](https://www.um.edu.mt/newspoint/learn/2026/dizzjunarjumtqedjinbenad-dizzjunarjunazzjonalital-malti.html)、[网站 About 页](https://dizzjunarju.mt/dwarna.html)、[公开字母索引 `lista.html`](https://dizzjunarju.mt/lista.html)）：
  1. **发布主体**：公告与 About 页归属于**马耳他大学马耳他语系（Department of Maltese, University of Malta）**；Antigravity 声称“由马耳他国家语言委员会 Kunsill + 马耳他大学联合发布，地位等同马来语 DBP PRPM”**缺乏官方页面证据支持**。
  2. **“唯一单语释义”系错误断言**：《Il-Miklem Malti》（十卷本）等马耳他语单语词典早已存在，不能称 `Dizzjunarju.mt` 是“唯一具备马耳他语单语释义的权威来源”。
  3. **当前公开可见规模**：本次实查其公开字母索引 [`https://dizzjunarju.mt/lista.html`](https://dizzjunarju.mt/lista.html) **仅列出 81 个词条链接**！虽不能断言其内部后台总量，但足以证明：**在未做覆盖率实测前，绝不能像 Step 323 那样宣称将其作为 15K 词典的全库一级校准底座**。
  4. **权限与 `robots.txt` 误区**：网站仅有版权页脚与隐私政策，未开放批量 API 或再分发许可；且根据 [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html)，`robots.txt` 规则**不是访问授权或版权/数据库复用许可**。

---

### 二、 前序对话（Steps 262 / 317 / 319 / 323）逐轮幻觉与摇摆审计

1. **Step 262（首次介绍与提问）**：
   - 将 `Għ` 和 `Ie` 并列称为“独立的一级字母分片”（混淆了 30 字母表、整词排序规则与 UI 分片）；
   - 将 `ie` 称为“双元音字母”（官方规范视作单一长元音的双字母字素 digraph）；
   - “闪米特核心层 ~35%，日常高频词 70%+，英语 10%+”缺失具体文献口径；
   - “Ġabra 16,000+ 核心词条、自带词根/十型/破碎复数”未标注快照版本且暗示全字段覆盖；
   - 把在 OPUS 2018/2024 中不存在 `mt` 包的 `OpenSubtitles` 列为词频源。
   - **归因纠偏**：v1.0 草案自述“Step 262 误写 `İ ż`”及“Step 262 出现 `komma / Karmenu Mallia / Ġużè Barbara`”与 Step 262 实际文本不符（Step 262 实际写的是 `Ż ż`，后三者来自上一轮研究提示词中的待核实项而非 Step 262 正文）。
2. **Step 317（第一次核查汇报）**：
   - 标题过度背书（“完整核实报告”“真实家底”），丢失了快照不可达、字段可选与许可限制；
   - 将 Comrie & Spagnol 的 1,500 项跨语义领域词表研究（闪语 56%、意/西 30.3%）误述为“核心高频基础词”；
   - 把 `MLRS/gabra-*` 源码仓库与 `maltese-verb-inflections` 小测试集写成可直接提取 19,831 词头的途径；
   - 提问选项中无依据写出“预计 12K–15K 独立词目”。
3. **Step 319（免爬虫直链回复）**：
   - 宣称“全部都有现成结构化文件直链，几分钟拉到本地”、“单靠直链包就已经拥有完整的词头、词根、变形表、英文释义、IPA 与词源”，犯了**本轮最明确的覆盖率与交付物形态过度承诺**。
4. **Step 323（资料四级分类与国家词典拉取建议）**：
   - 将自行设计的工程四级分类包装成“按词典学与史料标准”；
   - 无依据宣称“如果不拉取 `Dizzjunarju.mt` 就做不出学者级词典”，并在提问选项中推荐自动探测并拉取 `Dizzjunarju.mt` 缓存至 `data/dizzjunarju_raw/`，与 Step 317 的合规警告和 Step 319 的免爬虫承诺发生前后摇摆。

---

### 三、 语言学细节与例词逐一核查

1. **定冠词（`L-Artiklu`）与增音规则（v1.0 草案第 89 行存在 3 处错误/过度概括）**：
   - 九个太阳辅音（*konsonanti xemxin*：`ċ, d, n, r, s, t, x, ż, z`）列表**正确**（`j` 不在标准太阳辅音之列，如 `il-jum`）；
   - **术语错误**：增音元音的正确马耳他语语法术语是 **`vokali tal-leħen`**（而非 `vokali leħen`）；
   - **规则过度概括**：“遇双辅音词首增音为 `l-i...`”是错误的——只有特定辅音群（如 sibilant + 塞音 `skola → l-iskola`）需要 `vokali tal-leħen`，而 `il-ktieb`、`iż-żmien` 同样是双辅音起首却**不插 `i`**；
   - `għ/h` 起首词与冠词连用也并非无条件只有 `l-` 一种形式，且冠词还受前接词末尾元音影响。
2. **语法术语与例词核查**：
   - **`skola → iskejjel`（第 68 行）**：基本复数词形应写为 **`skola → skejjel`**（`iskejjel` 是带语境增音 `i` 的形式，不当作基础复数词头）；
   - **`Pronomi Mehmuża`（第 90 行）**：标准马耳他语学校语法通行标题应为 **`Pronomi Mehmużin`**；
   - **`m'għandix` / `x'inhu`（第 81 行）**：属于**标准正字法规范缩合**，不能仅归类为 WhatsApp 街头非正式“吞音连写”；
   - **`Times of Malta 马语版`（第 78 行）**：*Times of Malta* 是英语媒体，不存在所谓“Times of Malta 马语版”；
   - **`għ/h` 与 `ħ` 发音说明（第 52 行）**：不能将 `għ/h` 一概写死为“不发音”（特定位置或语境下会影响元音或实现为辅音），现代标准马耳他语对 `ħ` 常记为 `/h/` 或 `/ħ/`，须说明音标体系而非混写；
   - **`inizzja`、`beda`、`ħafer`、`skuża`（第 95 行）**：4 个词均为真实马耳他语词（`inizzja` 在马耳他法院判决书中有实证用例），但不能预先武断简化为固定的“日常 vs 正式”一刀切二分，且 `skuża`（含名词及“为……辩解/致歉”动词义）与 `ħafer`（原谅/宽恕）配价不同，不可无语境互换。
3. **本机 `Intl.Collator('mt')` 排序细节（第 112 行）**：
   - 本机 ICU `78.3` 的 `Intl.Collator('mt')` 虽已验证 `Għ` 在 `G` 与 `H` 之间、`Ie` 按 `i + e` 排序，但其默认 `ignorePunctuation` 为 `false`（如 `compare('a-b', 'ab') === -1`），不能将默认 `Intl.Collator('mt')` 直接等同于全部 DMS 200:2009 词典排序流程（需对连字符、撇号与定冠词前缀另做规范化处理）。
