# Open-Malti 马耳他语（Il-Malti）八维认知词典总体工程方案（v2.0 · 经 Codex 幻觉审计逐行修正版）

> **版本状态**：v2.0（已按 [codex_malti_hallucination_audit.md](file:///C:/Users/d/.gemini/antigravity/brain/060eff77-232d-4079-a013-677fea954056/codex_malti_hallucination_audit.md) 的逐行审计结论全量修正）  
> **核心铁律**：严格区分 **页面公布指标（Published Metadata）**、**本地已下载复算结果（Empirically Verified Counts）**、**工程设计取舍（Engineering Decisions）** 与 **待核实阻塞项（Pending Verification Blockers）**；撤回前序对话中“完整核实报告”、“直链包已具备完整字段”、“国家词典为唯一官方单语源且必须全拉”等过度承诺。

---

## 一、 前序对话（Steps 262 / 317 / 319 / 323）完整纠偏账本

以下根据 Codex CLI（`task-351`）对原始对话记录的逐字核查，如实列出前序各轮发言中的失实、夸大与前后摇摆（不虚构未在对应 Step 出现的错误，也不隐瞒后三轮的新增夸大）：

| 对话轮次 | 前序对话中的原话/表述 | Codex 独立审计结论与纠偏 |
| :--- | :--- | :--- |
| **Step 262**（首次介绍与提问） | 1. “双合字母 `Għ` 和 `Ie` 是独立的一级字母分片”<br>2. 将 `Ie` 称为“双元音字母”<br>3. “闪米特核心层 ~35%，日常高频词 70%+，英语 10%+”<br>4. “Ġabra 收录 16,000+ 核心词条与 480 万+ 屈折词形，自带词根/十型/破碎复数”<br>5. 将 `OpenSubtitles` 列为词频来源 | 1. **混淆概念**：标准字母表虽为 30 字母，但在整词排序（《Aġġornament》脚注 4、DMS 200:2009 §4.1）中仅 `Għ` 独立排在 G 与 H 之间，`Ie` 按 `i + e` 在 I 内部排序；UI 分片则属工程设计选择。<br>2. **术语不当**：官方规范将 `ie` 视为表示单一长元音的双字母字素（digraph）。<br>3. **缺失统计口径**：“高频词 70%+”无样本定义；Brincat 对 Aquilina 41,016 词目的统计为闪语 32.41%、西西里/意大利 52.46%、英语 6.12%。<br>4. **夸大覆盖率**：未注明 Ġabra 快照版本，且 Ġabra 官方声明其非完整词典、字段详略不一、大量屈折形系自动生成。<br>5. **数据源失实**：OPUS OpenSubtitles (2018/2024) 语言表均无 `mt` 包。<br>*(注：v1.0 草案曾误写 Step 262 含 `İ ż` 及 `komma/Mallia/Barbara`，经查 Step 262 原文实为 `Ż ż`，后三者源自后台检索提示词而非 Step 262 正文，特此更正归因。)* |
| **Step 317**（首次核查汇报） | 1. 自称“完整核实报告 / 真实家底”<br>2. 将 Comrie & Spagnol (1,500 项，闪语 56% / 意西 30.3%) 称为“核心高频基础词”<br>3. 称可通过 `MLRS/gabra-*` 与 `maltese-verb-inflections` 提取约 19,831 词头<br>4. 称 Kaikki 为“79,775 条记录”，并在提问选项中写“预计 12K–15K 独立词目” | 1. **过度背书**：隐去了快照下载待核、字段可选与许可证限制。<br>2. **研究性质误述**：Comrie & Spagnol (LWT) 系跨语义领域抽样词表研究，非按语料库词频排序的“高频词计数”。<br>3. **混淆仓库形态**：`MLRS/gabra-api` 是 API 源码仓库（其指向的上游 BSON 下载链接当前跳转马耳他大学首页）；`maltese-verb-inflections` 仅是少量动词的人工检查测试集（含未完成空文件），不能代表两万词头整库。<br>4. **指标失真**：`79,775` 是 Kaikki 页面公布的 `distinct words`（非 JSONL 行数，更非去重 lemma 数）；“预计 12K–15K”无实测依据。 |
| **Step 319**（免爬虫直链回复） | 1. “全部都有现成结构化文件直链，几分钟拉到本地”<br>2. “Tatoeba + WikiPron + MASRI G2P 规则表全部是 TSV / GitHub 现成文件直链”<br>3. “单靠直链包就已经拥有完整的词头、词根、变形表、英文释义、IPA 与词源” | 1. **夸大交付状态**：Ġabra 全量快照需验证可用镜像，HF `MLRS/korpus_malti` 有门控协议。<br>2. **混淆交付形态**：WikiPron `mlt_latn_broad.tsv`（清单标示 21,208 条）确为 TSV，但与 Kaikki 同源（均抽取自 Wiktionary）；MASRI `text2phon` 是 Python 代码接口；Mark Borg G2P 是 8 页 PDF 规则文档，并非即用 TSV。<br>3. **严重覆盖率过度承诺**：如 Kaikki 的 `kiteb` 条目并无统一顶层 `root` 字段（词根常散落于 `etymology_templates` 中且部分条目缺失或带抽取错误），UD_Maltese-MUDT 官方明确标注 `Lemmas: not available`、`Features: not available`。 |
| **Step 323**（资料四级分类与国家词典拉取） | 1. 称四级分类为“词典学与史料标准”<br>2. 称 `Dizzjunarju.mt` 由“马耳他大学 + Kunsill 联合发布，地位等同马来语 DBP PRPM”，且是“唯一具备官方马耳他语单语释义的来源”<br>3. 称 Kaikki“混杂约 6 万条变位词形”<br>4. 推荐探测并拉取 `Dizzjunarju.mt` 缓存在 `data/dizzjunarju_raw/` 作全库一级校准底座 | 1. **包装工程分类**：该四级表是本项目工程分层，非学界公认标准。<br>2. **拔高机构地位与排他性**：官方公告与 About 页显示 `Dizzjunarju.mt` 归属**马耳他大学马耳他语系**（未证实与 Kunsill 联合发布或具法定机构等同地位）；且《Il-Miklem Malti》等马耳他语单语词典早已存在，并非“唯一”。<br>3. **可见规模未查先吹**：实查 `https://dizzjunarju.mt/lista.html` 当前公开索引页面仅见 **81 个词条链接**；未核清其实际覆盖量与授权前，绝不能当作 15K 词典的全库底座。<br>4. **合规误区**：未确认公开批量 API 或再分发许可；`robots.txt`（RFC 9309）仅表达抓取偏好，绝非版权或数据库提取/改编授权。 |

---

## 二、 权威资料分级与合规获取方案（Data Architecture & Licensing）

### 1. 本项目工程资料四层架构（明确区分“规范/参考文档”与“机器可读数据包”）

| 工程层级 | 资料名称与真实形态 | 版本/公布指标（待本地下载复算） | 许可边界与合规红线 |
| :--- | :--- | :--- | :--- |
| **L1 法定正字法与排序规范文档** | 1. **Il-Kunsill Nazzjonali tal-Ilsien Malti** 官方规范文件：<br>- 《Aġġornament tal-Ortografija》<br>- 《Deċiżjonijiet 1》(2008 发布，2011 过渡期结束)<br>- 《Deċiżjonijiet 2 dwar il-Kitba tal-Kliem mill-Ingliż fil-Malti》(2018 发布，2023 过渡期结束)<br>2. **DMS 200:2009**（MSA 马耳他语区域与排序草案标准） | 官方公开 PDF 规范文档。 | 仅提取正字法规则、字母排序规则与规范示例词表作为校验准绳；不声称词典内容获 Kunsill 官方认证。 |
| **L2 学术与在线参考词典（非批量抓取源）** | 1. **`Dizzjunarju.mt`**（*Id-Dizzjunarju Nazzjonali tal-Malti*，马耳他大学马耳他语系 2026-06-19 启动）<br>2. **Joseph (Ġużè) Aquilina**《Maltese–English Dictionary》(2 卷，1987/1990，文献记载 41,016 词目) 及《English–Maltese Dictionary》(4 卷，1999–2000)<br>3. **Erin Serracino-Inglott**《Il-Miklem Malti》(1–9 卷 1975–1989；第 10 卷补编由 Mario Serracino-Inglott 于 2003 出版) | `Dizzjunarju.mt` 公开 `lista.html` 页面当前可见 81 个词条链接；纸本词典无官方公开全量 JSON。 | 版权归各出版方或马耳他大学所有。**严禁未经明确许可批量爬取 `Dizzjunarju.mt`（不将 `robots.txt` 当作授权替代，也不以“低频本地缓存+改写”规避数据库提取权）**；仅作人工抽检与规则参考。 |
| **L3 高校计算形态学与语料资源** | 1. **Ġabra 数据快照**（需核实并固定可用归档镜像 URL 与 SHA-256；区分 `MLRS/gabra-api` 源码仓库与底层 BSON/JSON 数据）<br>2. **Camilleri 动词变位测试集** (`johnjcamilleri/maltese-verb-inflections`，少量动词人工核查 CSV 测试集，含部分空文件)<br>3. **UD_Maltese-MUDT**（2,074 句、44,162 tokens CoNLL-U，注意官方标明 `Lemmas: not available`、`Features: not available`）<br>4. **MLRS Korpus Malti v4.0**（论文公布 466,601,373 tokens、20,758,071 句；HF `MLRS/korpus_malti` 默认仅含纯句子文本，需固定 revision） | 第三方 2026 打包快照曾报告 Ġabra 含 21,083 记录 / 19,831 词头，**必须以实际拉取的归档文件本地复算为准**。 | - Ġabra 前端现标数据 **CC BY 4.0**（2013 LREC 版为 CC BY 3.0，按实际快照版本保留对应许可与署名）<br>- `maltese-verb-inflections`：**MIT**<br>- `UD_Maltese-MUDT`：**CC BY-SA 4.0**<br>- `Korpus Malti`：**CC BY-NC-SA 4.0**（门控访问；是否可提取及发布派生统计词频须严格按 CC BY-NC-SA 4.0 正文及数据库权利条款核查，不预设自动豁免）。 |
| **L4 开源众包词典、发音与G2P候选组件** | 1. **Kaikki.org Wiktionary Maltese JSONL**（页面公布 `79,775 distinct words`，约 94.4 MB，2026-10-01 dump / 2026-10-25 抽取）<br>2. **WikiPron (`mlt_latn_broad.tsv` / `mlt_latn_broad_filtered.tsv`)**（官方 `summary.tsv` 标示 21,208 / 21,124 条；**注意与 Kaikki 同源于 Wiktionary，非独立第二信源**）<br>3. **G2P 候选组件**：`UMSpeech/MASRI` (`text2phon` Python 函数，待拉取实测) + Mark Borg 公开 G2P 规则（8 页 PDF 文档，需工程化实现并验证）<br>4. **Tatoeba (`mlt`)**（页面公布 699 句，非全部马英双语配对） | 全部指标需在阶段 0 下载固定快照后计算 SHA-256 并复算。 | - Kaikki 数据：**CC BY-SA 4.0**<br>- WikiPron：工具代码 **Apache 2.0**，`data/` 词表遵循 Wiktionary 许可（**CC BY-SA 4.0**）<br>- Tatoeba：按具体导出句集记录 **CC BY 2.0 FR** 或 **CC0**（音频单独核查许可）。 |

### 2. 阶段 0：资源可用性核验与数据摸底（Phase 0 Empirical Audit）
在承诺任何最终词库规模（如 5K、10K 或 15K）之前，必须先执行阶段 0 脚本，完成以下 **6 项硬核实** 并落盘 `data/audit/phase0_source_inventory.json`：
1. **资源存在性、版本与许可核验清单**：逐一验证上述公开数据包的下载可达性、固定版本号/commit、文件大小与 SHA-256；若 Ġabra 完整快照镜像不可达，明确标记为阻塞项，绝不用推测值替代。
2. **Kaikki JSONL 结构与去重分类实测**：
   - 统计 JSONL 总行数、按（`word` + `pos` + `etymology_number`）区分的词条数；
   - 区分纯屈折引用项（仅含 `form-of`）与**兼有独立词汇化义项的词条**（避免一刀切误删兼有独立义项的词形，并保留同形异源词）；
3. **Ġabra 快照真实字段覆盖率实测**：
   - 统计实际词头数、各字段（`root`/`għerq`、派生型 `verb_form`、复数、英文 gloss）的非空率，以及标记为 `hypothetical` / `pending` 或自动生成形式的比例；
4. **词源与词根提取路径实测**：
   - 在 Kaikki 中解析 `etymology_templates`（如 `mt-root`）、`head_templates` 与 `etymology_text`，分别统计“字段存在率”、“模板解析成功率”与“明确词源率”；对罗曼/英语借词将闪米特词根标为 **`not_applicable`（不适用）**，绝不与“缺失”混算；
5. **IPA 与 G2P 对照实测**：
   - 统计 Kaikki / WikiPron 中 Wiktionary 抽取 IPA 的覆盖率，并在该已有 IPA 集上实测 `MASRI text2phon` / Mark Borg G2P 规则的一致率与错误分布；
6. **语料分词与词形还原（Lemmatization）方案评估**：
   - 鉴于 `Korpus Malti` 与 `UD_Maltese-MUDT` 均无现成 lemma 标注，必须明确设计并抽检“分词 + 定冠词/附着代词剥离 + 基于 Ġabra/Kaikki 屈折表的 lemma 映射与同形词消歧”流程及误差率，再决定词频位序（Rank）生成方式。

---

## 三、 马耳他语专属「八维认知教学结构（8-Dimension Schema）」

针对马耳他语“**闪米特语法骨架 + 西西里/意大利罗曼词汇层 + 现代英语词汇层**”的特征，定制以下八大维度（全部平铺展示，0 手风琴折叠；所有不适用或无证据的字段必须留空 `null` 或标 `not_applicable`，严禁强行填充）：

### 第一维：基础标杆 (`headword`)
- **字段契约**：
  - `word`：符合 Kunsill 现行正字法的词头。动词一般采用第三人称阳性单数完成体（**`il-mamma`**，如 `kiteb`），**缺陷动词或不规则词项按词典实际引用形记录，不强行套用统一范式**。
  - `gender` 与 `collectivity`（分列独立字段，不混为同一分类轴）：
    - `gender`：`m.` / `f.` / `mf.` / `null`；
    - `collectivity`：区分集合名词（`kollettiv`）、个体名词（`isem tal-unità` / singulative）、双数（`imtenni`）与一般单复数。
  - `orthography_variants`：按适用决议条款（如 *Deċiżjonijiet 1* / *Deċiżjonijiet 2* 具体规则）及词典证据记录拼写变体与规范状态。
  - `syllables`：音节划分（无可靠依据者保留 `null`，严禁伪造）。
  - `ipa`、`ipa_scheme` 与 `ipa_source`：
    - 明确说明所采用的马耳他语音标分析体系（例如对 `ħ` 采用 `/h/` 还是 `/ħ/`，并在全库统一）；
    - 准确说明语境相关的发音规则（如 `għ` 与 `h` 在多数位置不独立发辅音但影响邻近元音音质与音长，在词尾或特定组合中可实现为咽音/擦音，**绝不笼统写死为“一概不发音”**）；
    - 来源诚实分级：`wiktionary_extracted`（Wiktionary/Kaikki 抽取音标）、`manually_reviewed`（人工核对音标）、`g2p_derived`（规则推导音标，待 G2P 准确率验收通过后启用）。
  - `rank` 与 `frequency_meta`：记录词频排名、语料来源、词形还原方法及消歧状态（未完成还原消歧者不标伪造排名）。
  - `source_presence` 与 `editorial_status`（将“外部词库收录关系”与“编审核验状态”解耦，不因两库同时收录但同源而夸大为“双重独立核实”）：
    - `source_presence`：如实记录数组 `['gabra', 'kaikki', 'ud_mudt', ...]`；
    - `editorial_status`：区分 `source_attested`（有开源词典/语料实证词条）与 `candidate_derived`（规则推导候选形式——**无实际词典或语料用例支持的候选形式不得作为正式已存在词头发布**）。

### 第二维：历时词源层 × 共时构词形态双轴模型 (`morphology`)
- **核心设计（将“历时词源层”与“共时构词机制”分列双轴，既严禁给借词伪造闪米特词根，也不排斥借词发生真实的闪米特模板同化）**：
  - `synchronic_Sync_pattern`（共时构词机制）：`'root_and_pattern'`（词根—词型非连续构词）、`'stem_affixation'`（词干缀合构词）、`'hybrid_assimilated'`（借词融入闪米特词根/破碎复数模板）、`'invariant'`（不变词）。
  - **当具备可分析的辅音词根（`għerq`）时**：
    - `root_consonants`：记录三辅音或四辅音词根（如 `k-t-b`、`għ-l-m`、`q-r-j`；注意双字母 **`għ` 是一个独立的根辅音单位**，在拆分与检索中不可按两个字符拆碎），支持点击检索同根词族（`#root:k-t-b`）；
    - `verb_form`：按**已证实存在的具体派生型**记录 **`Forma I–X`**（或四辅音 `Forma I–II`），**绝不机械为每个词根补齐不存在的十型**；
    - `plural_forms`：如实记录破碎复数（`plural miksur`，如 `ktieb → kotba`）或规则复数（`plural sħiħ`）。
  - **当为词干型或跨层同化借词时**：
    - `stem` (`zokk`) 与借词变位类别（如 `-a`、`-ja` 类，或完成体/未完成体特定人称中带 **`-ixx-`** 交替的类别，如 `issuġġerixxa`——按实际范式位置展示 `-ixx-` 交替，不写死为全格固定后缀）；
    - 若借词已融入破碎复数（如 **`skola → skejjel`**；带语境增音的形式 `l-iskejjel` 另行标注，不将 `iskejjel` 当作基础复数词头），如实展示其跨层形态同化。
  - `word_family`：有词典或语料证据支持的同根/同词干派生词芯片网格（一键跳词）。

### 第三维 & 第四维：来源释义与编审三语精解及地道搭配 (`senses` & `senses[].collocations`)
- **字段契约（严格区分“引用来源释义”、“编审翻译”与“原创编写说明”）**：
  - 每个义项包含 `id`、`pos`（词性主类与语法子类如动名词 `isem verbali`、被动/过去分词 `partiċipju passiv` 分离标注）；
  - `zh_definition`（中文编审释义）、`en_definition`（英文释义，标注系引自 Ġabra/Wiktionary 还是编审改写）、`mt_definition`（马耳他语解释，**显式标注 `definition_origin: 'authored_pedagogical' | 'licensed_source'`，严禁将模型编写的教学解释冒充为官方或纸本词典引文**）；
  - `nuances`：语义边界、配价（及物/不及物/介词搭配）与语境说明。
  - `senses[].collocations`（第四维）：每个义项提供地道实用的马-中-英三语短语搭配；发音按钮作为**条件增强功能**（仅在检测到可用 `mt-MT` 语音合成或已配置合法音频时激活播放，无可用马语语音时明确置灰提示，绝不拿英语/意大利语 TTS 冒充马耳他语发音）。

### 第五维：双境语用对照 (`dual_scenarios`)
- **正式书面语境（`formal` · Aħbarijiet / Dokumenti / UE）**：
  - 采用或参考真实马耳他语媒体（如 **TVM News**、*L-Orizzont*、*Illum*）、学术或欧盟公文语境的标准马耳他语例句（明确标注 `source_type: 'corpus_attested' | 'pedagogical_example'`；注：*Times of Malta* 为英语日报，不虚构“Times of Malta 马语版”）。
- **日常会话模拟（`colloquial` · Konversazzjoni ta' Kuljum / Minglish）**：
  - 明确标注为 **编写的教学模拟对话（`pedagogical_dialogue`）**（除非有明确出处的真实语料实录）；
  - **准确区分“标准正字法缩合”与“口语/语码转换特征”**：
    - 如 `m'għandix`、`x'inhu` 属于**标准马耳他语规范缩合形式**，在教学中标为标准缩合语法点，不误导为“非标准聊天吞音”；
    - 若展示马耳他语—英语语码转换（Minglish），须有真实语用依据并给出自然对应的纯马耳他语表达参考（不强求唯一机械标准答案）。

### 第六维：核心屈折、定冠词形式与附着代词 (`inflection_and_clitics`)
1. **核心变位/复数速查表（仅展示适用且有证据的格，缺陷范式、无对应阴阳形或无双数者允许留空/标不适用）**：
   - 动词：展示已核实的完成体基准形（`Perfett 3sg.m` = `il-mamma`）、未完成体（`Imperfett 3sg.m`）、命令式（`Imperattiv`）与否定构式（`ma ... -x`）；
   - 名词/形容词：展示实际存在的单数（阳/阴）、复数（明确标出 `Plural Miksur` 破碎复数或 `Plural Sħiħ` 规则复数）及双数/集合名词关系（如 `miktub` 准确说明为“写成的、被写的”被动/过去分词）。
2. **定冠词形式（`L-Artiklu` · 按词项及语境记录，绝不单靠首字符无条件机械生成）**：
   - 定冠词的形式按词项及语境记录。标准太阳辅音（*konsonanti xemxin*）为 **`ċ, d, n, r, s, t, x, ż, z`**，例如 `ix-xemx`、`iż-żmien`；`j` 通常不发生这种同化，例如 **`il-jum`**。
   - 元音起首以及 `għ` / `h` 起首词的冠词形式须按适用规则和语境处理（如 `l-għajn`，官方教学规范亦区分带与不带增音 `i` 的语境形式）。
   - 部分词需要增音 `i`（**`vokali tal-leħen`**），例如 `l-iskola`，但**绝不能将所有双辅音群统一处理为 `l-i-`**（例如 **`il-ktieb`**、**`iż-żmien`** 均不插 `i`），且冠词形式还受前接词末尾元音影响。因此必须保存有来源的实际形式及必要语境变体。
3. **附着代词（`Pronomi Mehmużin`）**：
   - 采用马耳他语学校语法通行标题 **`Pronomi Mehmużin`**；
   - 针对适用介词/拟动词（如 `għand → għandi / għandek / għandu`，明确区分介词用法与表“拥有”的占有构式功能）、高频亲属/身体名词与及物动词，逐词记录**实际词干变化后的真实形式及其句法功能**，绝不机械拼接后缀。

### 第七维：语域、同义词配价辨析与跨语种同源/假朋友对照 (`pragmatics_and_cognates`)
- `register`：基于词典或语料证据标注语域（正式法规/公文、日常通用、宗教、古旧或俚语）。
- `synonym_and_doublet_contrast`（近义词与双层词对比，**按实证义项、配价与语境比较，不预先武断套用“闪语必口语、借词必正式”的刻板二分**）：
  - 例如对比 `beda`（通用“开始”）与 `inizzja`（见于法院判决书等法律/程序语境“提起、启动”）；
  - 对比 `ħafer`（原谅、宽恕）与 `skuża`（兼有名词“借口/歉意”及动词“为……辩解、致歉/原谅”义），明确区分二者的语义重心与句法配价，不作无语境互换。
- `cognates_and_false_friends`：
  - 严格区分 **历史继承（Inherited from Siculo-Arabic）**、**同源对映（Cognate with Classical/Modern Arabic，绝不把现代标准阿拉伯语对应词误写成直接借入源）**、**直接借入（Borrowed from Sicilian / Italian / English）**、**语义借译（Calque）** 与 **假朋友（False Friends）**。

### 第八维：历史词源链与认知助记 (`etymology`)
- `stratum`：标注词源层（`Siculo-Arabic / Semitic`、`Sicilian / Italian (Romance)`、`English`、`Other` 或 `Uncertain`）。
- `source_chain`：仅记录有词源学证据支持的传播链；**当具体单词缺乏确切历史借入年代或传播事件证据时，保持留空，绝不按所属词汇层自动套写“骑士团时期/英国海军时期”等宏观历史故事**。
- `cognitive_memory_aid`：显式标识为学习者助记口诀（与历史词源考据严格视觉隔离）。

---

## 四、 正字法、排序与 Web 静态分片工程规范

1. **Unicode 规范化与双轨检索（`worker.js`）**：
   - 全库统一使用 NFC 规范化编码，完整保留 `Ċ/ċ, Ġ/ġ, Għ/għ, Ħ/ħ, Ie/ie, Ż/ż`、重音符、撇号（`'` / `’`）与连字符；
   - 搜索索引建立 **精确字素检索轨（区分 `ż/z`, `ħ/h`, `ġ/g`, `ċ/c`, `għ/gh`）** 与 **ASCII 容错轨（包含 `gh → għ` 专门映射及 `ċ→c, ġ→g, ħ→h, ż→z` 折叠）**，支持输入 `zminijiet` 或 `ghajn` 命中 `żminijiet` 与 `għajn`（检索耗时作为本地基准测试指标验收）。
2. **排序与 UI 字母分组规范**：
   - **排序实现**：本机 Node 24.19 / ICU 78.3 下 `new Intl.Collator('mt')` 虽已验证满足 `G < Għ < H` 与 `Ie` 按 `i + e` 排序，但其默认 `ignorePunctuation` 为 `false`（`compare('a-b', 'ab') === -1`）。因此必须封装专用的 **`compareMalteseHeadwords(a, b)`** 函数，在调用 `Intl.Collator('mt')` 前对定冠词前缀、连字符与撇号执行显式规范化与二级决胜（tie-breaker）测试！
   - **UI 导航分组（工程设计选择）**：左栏提供 **29 个字母分组加 `#`（共 30 个一级入口按钮：`A, B, Ċ, D, E, F, Ġ, G, Għ, H, Ħ, I, J, K, L, M, N, O, P, Q, R, S, T, U, V, W, X, Ż, Z, #`）**，并在 `I` 分组下的二级双字母前缀条（`#sub-prefix-bar`）中突出展示 `ie` 前缀胶囊。
3. **前端浏览台组件复用与新增验收**：
   - 拟复用已在 `Open-Lexicon`（commit `9a6d303`）与 `Open-Melayu`（commit `162beb2f8`）通过验收的前端浏览台组件架构，并针对马耳他语新增专项单元测试与真机 Chrome E2E 验收（不将旧项目的通过记录自动继承为马耳他语项目的通过结论）。

---

## 五、 实施路线图与双轨出厂门禁（软件工程门禁 + 语言学内容门禁）

1. **阶段 0（资源存在性、许可与家底实测）**：
   - 执行逐资源可达性、版本固定、SHA-256 与许可证核查；对已取得的数据包运行统计脚本，生成包含真实去重数、字段覆盖率与阻塞项的 `data/audit/phase0_source_inventory.json`，交由用户审阅后拍板词库目标规模。
2. **阶段 1（词池锁定、词形还原消歧与浏览台搭建）**：
   - 完成候选词池构建与抽检，搭建马耳他语独立仓库与本地静态服务（端口 `8767`）。
3. **阶段 2（受控微批编纂与双轨五项门禁验收）**：
   - **Gate 1（正字法与 Unicode 规范门禁）**：NFC 规范化、0 控制字符、`Ċ/Ġ/Għ/Ħ/Ie/Ż` 拼写与撇号/连字符规范、动词引用形及例外词头核查通过；
   - **Gate 2（历时词源 × 共时形态双轴诚实门禁）**：0 伪造借词闪米特词根，同时正确容纳有证据的跨层同化形式（如 `skola → skejjel`），不机械补齐不存在的动词十型或缺陷范式；
   - **Gate 3（定冠词、附着代词与语法准确性门禁）**：`vokali tal-leħen`、`L-Artiklu` 与 `Pronomi Mehmużin` 逐词符合真实马耳他语语法与语境，0 全辅音群一刀切 `l-i-` 错误；
   - **Gate 4（来源级别、版权合规与证据支持门禁）**：每项来源标签、IPA 标注与释义分类均有直接对应的本库证据支持，0 假冒官方/纸本引文，0 未授权爬取或违反 NC/SA 条款的数据混入；
   - **Gate 5（软件工程与内容抽检双验收门禁）**：三态守恒账本 + 排序/检索/UI 单元测试 + 真机 Chrome E2E 100% 通过，并附分片内容抽检报告与已知覆盖边界说明。
