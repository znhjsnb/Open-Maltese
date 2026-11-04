# Open-Malti · 马耳他语认知词典

马耳他语、中文、英语八维学习工作台。提供 24,045 个来源词头检索、124,488 个词形反查键，以及 Phase 2 首批 100 个三语教学词条。教学内容明确标为原创，`phase2_reviewed` 表示本批编审，不冒充母语专家认证；缺证维度仍可为空。Phase 3 双栏工作台已实现，真实 Chrome、视觉与听音验收待宿主完成。

## 本机使用

仅需 Python 3.10+；构建与 HTTP 服务均使用标准库，无数据库或付费 API。

```powershell
Set-Location C:\Users\d\Documents\open-malti
python -X utf8 scripts/phase0_inventory_audit.py
python -X utf8 scripts/build_phase1_shards.py
python -X utf8 scripts/phase2_quality_gates.py
python -X utf8 -m unittest discover -s tests -v
node tests/phase1_client_checks.mjs
node tests/frontend.browser.mjs
python -X utf8 app/server.py
```

打开 **http://127.0.0.1:8767**。换端口可用 `python app/server.py --port 8768`。服务器只公开 `app/static/`，绑定本机回环地址。Node.js 可运行额外的 Worker / 音频逻辑检查；无 Node 时，该项会明确跳过，Python 构建、服务与其余测试不依赖 Node。

Windows 阅读 Markdown 使用 `Get-Content -Encoding UTF8`。通过 PowerShell 管道传递中文或 Maltese 文本时，还需先设置 `$OutputEncoding = [System.Text.UTF8Encoding]::new($false)`。

## 数据家底与三个词库层级

Phase 0 原始审计报告在 `data/audit/`：Ġabra 有 21,083 条记录、19,831 个唯一原始词头；Kaikki 有 80,790 行。经过既有异常项排除和词位分类，精确拼写并集为 **24,345**，规范化并集为 **24,045**。这些是本地快照复算结果，不代表人工编审完成量。

Phase 1 的最新统计与样例在 [data/seed/lemma_pool_summary.json](data/seed/lemma_pool_summary.json)。当前实测：

| 层级 | 资格 | 词头数 |
| --- | --- | ---: |
| Tier 1 双源核心 | Ġabra 与 Kaikki 均有独立词位 | 5,051 |
| Tier 2 单源丰富 | Kaikki-only 独立词位 4,516；或 Ġabra-only 同一记录具备有效实证词根、音标、英文释义 6,898 | 11,414 |
| Tier 3 基础词库 | 其余 Ġabra 来源词头 | 7,580 |
| 合计 | 规范化词头，无补造词头 | **24,045** |

Tier 1+2 实测 **16,465**，而非设计时估算的约 15,000。保留实际资格规则，不裁掉有据词目来凑数。`tier` 表示编纂优先级；`source_presence` 表示来源收录关系；`editorial_status=source_attested` 不表示人工审校或两份独立证据。

当前有 **10,138** 个词头带实证词根，形成 **1,686** 个根组。历史词源分类只使用明确供体语言的词源模板或词源文本；共时词根不会自动提升为历史闪米特词源。只有实证词根时，保留 `root_status=attested`、`pattern_type=root_and_pattern` 与 `stratum=unspecified`。本次词头汇总的历史语源计数为：闪米特 2,724、罗曼 3,921、英语 264、其他/混合 93、待核 17,043。来源音标保留原有转写，`ipa_scheme=source_transcription_preserved`，不宣称不同来源已统一音系分析。

## 构建与检索结构

```text
data/raw/ → scripts/build_phase1_shards.py
           ├─ data/seed/lemma_pool_summary.json       Git 跟踪
           └─ app/static/data/                      生成产物，Git 忽略
              ├─ manifest.json
              ├─ index_lite.json
              ├─ wordforms_lookup.json
              └─ shards/shard_<ASCII bucket>.json    30 片

app/server.py → 静态页面 → Web Worker 检索 → 按需读取词条分片
```

构建复用 Phase 0 的 MDX 解析、词位分类、词根提取、DMS 排序与 Unicode 规范化。原始快照必须在 `data/raw/`：Ġabra ZIP、Kaikki JSONL、WikiPron TSV、Camilleri CSV 目录。若存在 Phase 0 的 Ġabra 仓库镜像，仍校验其 MDX 与 ZIP 一致；Phase 1 不强制另装该镜像，Phase 0 默认核验行为保持不变。构建不联网、不改原始数据或 Phase 0 审计 JSON。可用 `--raw`、`--output`、`--summary` 指定输入与输出位置。

当前版本使用 `malti-phase2-2026-11-03-<叠加文件摘要>`，叠加内容变化会更新缓存代际。以上第一条 Python 命令会按修正后的规则重建两份内容相同的 Phase 0 审计报告；第二条重建 Phase 1。Phase 0 还需要交接清单中的 MASRI、UD、Tatoeba 等本地辅助资料。固定输入校验和如下，不能以更新的上游下载静默替换：

| 本地输入（`data/raw/` 内） | SHA-256 |
| --- | --- |
| `GabraMalteseDict_MDX_v1.0.zip` | `56b03ed1827d782d27ad148dca95a50add79ffda05ceff134fb66a92d8c4b88f` |
| ZIP 中的 `Gabra.mdx` | `93188e96ae19d540d50f952fd9fe0262900e3cca583145d44340428f3202808d` |
| `kaikki.org-dictionary-Maltese.jsonl` | `0627068191ed5a36a893817c1bf051fdc2e430a89d54a42808ce3a92d60495ff` |
| `mlt_latn_broad.tsv` | `3666b5d67aa25e5001fc9ded4de80ab296bd2fbe2e87c71465ac1dd01022766f` |

完整 Phase 0 来源校验和在 [审计报告](data/audit/phase0_source_inventory.json) 的 `source_files_inventory`。Phase 1 manifest 的 `raw_source_sha256` 另外逐文件记录实际使用的 Camilleri CSV 等输入；每个生成索引和分片均附字节数与 SHA-256。可用 `Get-FileHash -Algorithm SHA256 data/raw/kaikki.org-dictionary-Maltese.jsonl` 核对固定文件。恢复生成产物时保留 `data/raw/`，重新执行上面的审计、构建、测试命令；无需删除浏览器缓存。

清洁词头列表仅列来源独立词位池。Kaikki 的 **69,617** 行纯词形、**896** 行替代拼写，加上 `forms` 表和词池内 Camilleri 动词变位，组成当前 **124,488** 个表面形反查键。保留同形多解、来源标签及语法标记；按显式引用和来源表连接，不猜造词干。

示例：`ktibt → kiteb`、`kotba → ktieb`、`kun → kien`、`ix-xemx → xemx`、`l-iskola → skola`、`fil-ktieb → ktieb`、`m'għandix → għand`。后几项有审计文档中的显式语法参考，标签为 `grammar_reference`，不冒充词典中原有的词形行。一般冠词、融合介词和前附着成分只剥离一次，再匹配已有实证词头或反查表。

仍有 **10** 行来源引用无法连接到既有词池，例如目标本身缺失或引用带抽取异常；其数量与全部样例列在 summary，未虚构目标补齐。Camilleri 的原始有效形式有 54,464 条，其中 53,512 条所属动词在当前词池内并已索引；同名修订文件的重复形式合并，语法与来源信息保留。

主导航为 29 个一级字母加 `#`，另有“全部”；`IE` 在 `I` 桶中作为优先展示的 `ie` 前缀。`għ` 按单一字素处理；`ie` 整词排序按 DMS 的 `i+e` 处理。文件名使用 `GH`、`C_DOT`、`G_DOT`、`H_BAR`、`Z_DOT`、`HASH`，manifest 显式映射，不依赖操作系统大小写或 Unicode 文件名处理。

Worker 维护精确拼写与 ASCII 容错检索，分页返回 60 条。点击 `#root:k-t-b` 可查同根词；词族最多展示 16 个有据词头。页面用请求序号隔离过期的检索、错误与分片响应。Worker 第一阶段仅载入 `index_lite.json`，立即开放词头与冠词规则搜索；第二阶段后台载入反查表，完成后重跑当前查询并更新徽章。反查文件为 `{"version":...,"tags":[...],"forms":{"ktibt":[["kiteb",0]],...}}`，整数引用共享来源/语法描述，约 **4.34 MB**（当前精确字节数见 manifest），保留全部 124,488 个表面形。标签不再重复嵌入已由键和值确定的表面拼写、目标词头。

索引和分片缓存以 manifest **版本 + SHA-256** 为键并校验内容。IndexedDB 自动保存 manifest、两份索引及已访问分片；点击侧栏“准备离线词库”会按当前固定版本依次保存全部 **32 项资产（2 个索引 + 30 分片）**，逐项校验摘要并在写入 `files` 后回读。再次点击可暂停，续传会跳过已校验保存的资产；存储拒绝或回读失败时会提示重试，不会仅因下载完成就宣称离线就绪。数据库 v2 仍能读取原 `assets` 缓存。Service Worker 保持页面模块及 `/data/` 的网络优先与离线回退；音频不属于这 32 项资产，仍需网络。尚未访问或离线准备未覆盖的分片仍需联网；反查表载入失败时基础搜索继续可用。重建后刷新页面即可按新 manifest 加载，等待新 SW 激活时可关闭旧标签后重开。实际浏览器离线及性能门禁仍待执行。

## Phase 3 工作台

侧栏支持 DMS 200 正序、逆序与 Tier 排序、收藏筛选、每批 60 条流式追加及页码跳转。空收藏精确显示 0 个词目，第二阶段反查表回放会替换已有页。栏宽可拖拽、方向键调整或双击复原，设置仅保存在本项目的本机键名中。

阅读区保留八维平铺，义项胶囊可跳转并短暂强调对应义项，词头滚出视野后显示在工具栏。“排版”可调整四种纸张、字族、密度、字号及语言模式，与既有控件共用 `open-malti-preferences`，旧偏好自动迁移。每日一词及抽认卡使用当前结果中的真实条目，支持点击或键盘翻面、拖动把手下滑关闭；减少动态效果时使用透明度切换。

多子词位条目的 06/08 按来源记录 id 隔离，缺失形式保持空缺。屈折节选标明展示 / 总条数，来源英文和教学译释分别标注归属，助记与历史词源分区显示。详细契约和宿主验收矩阵见 [Phase 3 方案](docs/PHASE3_WORKBENCH_PORT_PLAN.md)。

太阳冠词及融合介词仅在辅音与词干首辅音一致时剥离；太阴前缀拒绝太阳辅音起首。支持 `fix-xemx`、`bid-dar`、`lill-kelb`、`x-xemx`、`d-dar`，拒绝 `ix-ktieb`。增音 `i` 仅在指定咝音辅音群及实存词头匹配时剥离，优先保留实存的 `i...` 词头。提示条区分 `grammar_rule`、`grammar_reference` 与词库来源变位。DMS 排序为数字先于字母、大写先于小写。

## Phase 2 批次与五道门

首批文件为 [phase2_tier1_batch1.json](data/enriched/phase2_tier1_batch1.json)：保留原 25 个展示词，新增 75 个 Tier 1 词，共 100 词、200 组搭配、200 段场景及 413 个按词性和原英文义项逐项绑定的中文译释。原展示词 `bongu`（Tier 3）、`għand`（Tier 2）保留原层级，其余 98 词均为 Tier 1；分层从未为凑数而修改。

完整构建按文件名排序加载 `data/enriched/*.json`，重复键、未知键、来源证据改写和缺少义项译释都会拒绝。只添加教学义项、译释、搭配、场景、助记与冠词；保留英文来源释义及 `translation_provenance` 的独立归属。`skola → skejjel` 的实证破碎复数在基础构建器标为 `hybrid_assimilated`，词根仍为空。发布时将来源格式控制字符转为空格，损坏的问号释义明确标为 `[unreadable source text]`；数量记录于 summary/manifest 的 `source_text_repairs`，原始文件不变。

```powershell
# 后续修改叠加文件后快速同步，不重新解析原始词库
python -X utf8 scripts/run_phase2_enrichment.py --sync
# 或直接调用同步器，再单独写报告
python -X utf8 scripts/sync_enriched_to_shards.py
python -X utf8 scripts/run_phase2_enrichment.py --validate-only
# 仅准备下一批的来源材料，不调用模型
python -X utf8 scripts/run_phase2_enrichment.py --batch-size 25
# 将准备材料经 UTF-8 stdin 交给本机 Codex CLI（显式 opt-in）
python -X utf8 scripts/run_phase2_enrichment.py --batch-size 25 --dispatch
```

快速同步与完整构建共用叠加器、版本计算和序列化，测试逐字节比较分片、索引、manifest 和 summary。生成文件 `app/static/data/phase2_baseline.json` 用于撤销/重应用叠加；缺失时须先完整构建。该缓存不改变原始数据的权威性。同步也更新紧凑反查表的版本字段与摘要，表面形数量不变。所有内容文件先写入，manifest 最后更新；更新中途的读者由摘要检查拒绝混合版本，刷新后重试。

Phase 2 的 `colloquial` 保留整段 `mt/en/zh`，并须提供至少两轮 `messages`，每轮包含 `speaker`（姓名＋中文社会角色）、`mt_spoken`、`mt_standard`、`en`、`zh`。标准表达已经规范时可与口语相同，规范缩合不应误标为非标准形式。反稀释门同时要求：逐实证义项中文译释、至少两个不同三语搭配、至少八字符的助记。首批 100 条已升级；baseline 保持叠加前的来源记录，避免撤销时遗留精编数据。

宿主执行的持续滑动队列与 A/B 基准（这些命令会调用本机订阅 Codex CLI）：

```powershell
python -X utf8 scripts/run_phase2_ab_benchmark.py
python -X utf8 scripts/run_phase2_sliding_queue.py --slots 25 --batch-size 4 --timeout 420 --max-words 0 --milestone-interval 100 --wave all
```

队列在每组内部沿用 `index_lite.json` 的 DMS 顺序：先 Tier 1/2 中有录音的未精编词，再其余 Tier 1（Wave 1），最后其余 Tier 2（Wave 2）；`--wave 2` 只取最后一组。完整 Wave 1 为 5,384，Tier 1+2 为 16,465，实际剩余数扣除已精编和隔离词。`--max-words` 限制新选词数，重试不重复计数。只读 worker 经 UTF-8 stdin 接收紧凑来源包和原样 POS/英文选择器，返回 JSON，由单一控制线程逐词验证和落盘；有空槽立即补位，每累计 100 个成功词同步并运行五门。失败项优先两词重试（360 秒），初次失败加三次重试仍失败才写 `data/audit/quarantine_words.json`。控制器不自动提交 Git。

A/B 取接下来 80 个 Wave-1 候选，偶数索引分给 A（10×4，420 秒），奇数索引分给 B（5×8，840 秒），15 批并行；失败词再做一轮两词重试。成功词按原队列顺序写 `data/enriched/phase2_tier1_batch2_ab.json`，重新执行可追加后续候选，不覆盖先前成果。报告在 `data/audit/phase2_ab_benchmark_report.json`，包含耗时、吞吐、首轮通过率、输入字符节省、内容长度、真实分类分布以及 B 前后四词的首轮比较。交错分组不保证分类分布完全相同，报告会明确记录；token 数仅为字符数÷4 的估算。最终机器五门、母语内容和浏览器验收分别记录，当前沙箱不执行真实模型基准或 Chrome。

[五门报告](data/audit/phase2_quality_gate_report.json) 无时间戳，包含逐门 pass/fail、错误及按 Tier/词源层/丰富状态固定哈希抽取的教学样本。门禁检查 Unicode、形态来源诚实、冠词/实证代词、许可/教学归属和守恒；不能以确定性程序替代母语语言学抽检与听音。Chrome 回归单独执行并单独记录。

冠词引擎输出引用语境形式，处理咝音辅音群增音、`żmien` 例外、`j` 太阴字母、`għ/h` 语境提示，不宣称穷尽连续话语的全部变体。规则依据保留在 [主方案 Gate 3](docs/MASTER_PLAN_V2.md#gate-3)，一手参考为[马耳他大学 A1 教学大纲](https://www.um.edu.mt/library/oar/bitstream/123456789/138501/1/Maltese_for_foreigners_syllabus_level_A1_beginners_elementary_2017.pdf)与[Kunsill《Tagħrif》](https://kunsilltalmalti.gov.mt/wp-content/uploads/2023/03/taghrif.pdf)。

## 阅读与导出

八维信息默认平铺；没有折叠面板。每个规范化拼写仍只有一个列表入口，详情中的 `lexeme_analyses` 按来源记录、词性与 `etymology_number` 保留独立形态、词根、IPA、历史词源及义项。例如 `dar` 的房子义及 `djar` 与转动义及 `jdur / midur` 分开呈现；来源本身没有词根时保持空值。`plural_forms` 仅包含有名词性分析支持的词汇复数，不含动词人称、否定或代词连写变位。

提供四种纸张主题、字号、马–中–英 / English–Maltese 切换、Markdown 和 Anki TSV 复制。Anki 的九列是词头、IPA、英文释义、中文释义、含许可与链接的来源、Tier、审核状态、Commons 录音署名链接、分开的子词位分析；Markdown 同样携带来源与待审标签。导出只包含录音文件页链接，不复制录音文件。

快捷键：`/` 聚焦搜索、`↑ / ↓` 切词、`Esc` 关闭发音指南。筛选可叠加；无结果时可切回“全部”与“全部语源”。点击同根词或根标签会清除旧筛选再查询。

筛选包含全部词头、Tier 1 双源核心、Tier 1+2 候选池（16,465）、精选样板（100，随 manifest 动态更新）、有闪米特词根、罗曼/英语借词、有真人发音，以及各历史词源层。“有闪米特词根”表示实证共时辅音词根，历史词源仍可能待核。

## 发音依赖与诚实降级

1. **真人录音**：优先播放 Kaikki 中的 Wikimedia `mp3_url` / `ogg_url`。原始快照 **720 行**带音频，并非 720 个独立词位；规范化并限定当前独立词位池后，**597 个词头**有可用录音 URL。方言说明、文件名和个别文件的许可提示随条目保留。录音需要网络，播放失败会继续尝试马语合成。
2. **原生马语 TTS**：只接受浏览器实际枚举出的 `mt-MT` / `mt` / `mlt` 语音，等待异步 `voiceschanged` 后再判断。明确选择该 voice 并设置 `lang='mt-MT'`，不用英语、意大利语或默认 voice 替代。
3. **发音指南**：没有可用马语语音时展示来源 IPA，或词中实际出现的特殊字素提示及安装说明。字素提示是教学概述，不是规则生成的实证音标。

[Microsoft 官方语言列表](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support)列有 Grace 与 Joseph 马耳他语语音；可在 Edge 的朗读语音选项中检查是否可用。[Edge 朗读功能](https://explore.microsoft.com/en-us/edge/features/read-aloud)提供自己的语音选择界面。**这些名单不保证每台设备的网页 `speechSynthesis` 接口会暴露同一组语音。**工作台以实际 [getVoices()](https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesis/getVoices) 与 [voiceschanged](https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesis/voiceschanged_event) 结果为准。

本机检测：

```powershell
powershell -NoProfile -File scripts/check_maltese_tts.ps1
```

脚本仅检测 PATH 中的 eSpeak-NG 与 Windows System.Speech，不安装软件或修改设置。eSpeak-NG 的[官方语言表](https://github.com/espeak-ng/espeak-ng/blob/master/docs/languages.md)包含 `mt`；可从[官方 Releases](https://github.com/espeak-ng/espeak-ng/releases)安装后运行：

```powershell
espeak-ng --voices=mt
espeak-ng -v mt "ktieb"
```

命令行引擎可用不等于浏览器已安装 voice；系统语音接口还需支持并暴露该引擎。没有可用系统包时保留 IPA 指南与真人录音即可。首次检测本机未发现 eSpeak-NG 或 System.Speech 的马语 voice；浏览器语音和真实播放尚待人工/Antigravity 门禁。

## 来源、许可与验收边界

- Ġabra 本地 MDX 快照：**CC BY 3.0**，依 Camilleri 2013 Appendix D 与[打包署名说明](data/raw/gabra-maltese-dictionary/docs/ATTRIBUTION.md)，保留 Ġabra、John J. Camilleri 及贡献者、快照整理者 Jingyuan Zheng 的署名，注明打包方的 `aħwa` 修正。上游现网标 CC BY 4.0，不据此重标本地快照。
- Kaikki / English Wiktionary：CC BY-SA 4.0；词条、词源和派生数据保留来源。WikiPron 数据同样源自 Wiktionary，不算独立第二信源。
- John J. Camilleri 的 `maltese-verb-inflections`：按本地 `LICENSE` 为 MIT；不沿用早期交接中误写的 CC BY-SA 3.0。
- 每条录音均有 `audio_file` 与可点击的 `audio_commons_url`，作者及许可查看各自 Commons 文件页，不能把文本许可统一套到音频。卡片及两种导出均保留该链接。
- 未使用 UD 学习记录或 Korpus Malti 门控语料，也未抓取 Dizzjunarju.mt。

当前回归：`python -X utf8 -m unittest discover -s tests -v` 为 **117 项通过、0 失败、0 跳过**（[日志](tests/artifacts/phase3_unittest.log)），`node tests/phase1_client_checks.mjs` 为 **55 项通过**，包含原 37 项和 Phase 3 新增契约。本轮未重建或改动数据，32 项发布资产的摘要全部匹配清单。

软件测试覆盖真实构建、24,045 守恒、30 桶、字段空值与来源、词形反查、Worker 排序/筛选、音频三分支与失败降级、HTTP 服务及目录边界。`node tests/phase1_client_checks.mjs` 可单独运行客户端行为检查。

最终 Chrome E2E（现有 PASS 1–8 加新增 PASS 9–12）、实际听音、移动端与视觉验收仍按 [RULES.md](RULES.md) 由 Antigravity 执行；本批客户端离线及 SW 检查使用 Node 隔离测试环境，未宣称真机浏览器门禁完成。代码与测试待 Antigravity 审查并提交。
