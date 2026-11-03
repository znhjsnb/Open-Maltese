# Open-Malti · 马耳他语认知词典

马耳他语、中文、英语八维学习工作台。Phase 1 提供全量来源词头检索、词形反查和 25 个教学展示词；扩展内容缺证时保留 `null`。中文教学释义、搭配和例句均独立标为原创教学内容，仍待 Phase 2 语言学复核。

## 本机使用

仅需 Python 3.10+；构建与 HTTP 服务均使用标准库，无数据库或付费 API。

```powershell
Set-Location C:\Users\d\Documents\open-malti
python -X utf8 scripts/phase0_inventory_audit.py
python -X utf8 scripts/build_phase1_shards.py
python -m unittest discover -s tests -v
node tests/phase1_client_checks.mjs
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

当前生成版本为 `malti-phase1-2026-11-03-r2`。以上第一条 Python 命令会按修正后的规则重建两份内容相同的 Phase 0 审计报告；第二条重建 Phase 1。Phase 0 还需要交接清单中的 MASRI、UD、Tatoeba 等本地辅助资料。固定输入校验和如下，不能以更新的上游下载静默替换：

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

Worker 维护精确拼写与 ASCII 容错检索，分页返回 60 条。点击 `#root:k-t-b` 可查同根词；词族最多展示 16 个有据词头。页面用请求序号隔离过期的检索、错误与分片响应。Worker 第一阶段仅载入 `index_lite.json`，立即开放词头与冠词规则搜索；第二阶段后台载入反查表，完成后重跑当前查询并更新徽章。反查文件为 `{"version":...,"tags":[...],"forms":{"ktibt":[["kiteb",0]],...}}`，整数引用共享来源/语法描述，实际 **4,338,881 字节（4.34 MB）**，保留全部 124,488 个表面形。标签不再重复嵌入已由键和值确定的表面拼写、目标词头。

索引和分片缓存以 manifest **版本 + SHA-256** 为键并校验内容。IndexedDB 保存 manifest、两份索引及已访问分片，Service Worker 为页面模块、manifest 和数据请求提供网络优先与离线回退；离线刷新可以恢复已缓存词库。首次在线准备后才有离线数据，未访问分片和未完成下载的反查表仍需联网；第二阶段失败时基础搜索继续可用，不会借用旧代际的反查表。重建后刷新页面即可按新 manifest 加载，等待新 SW 激活时可关闭旧标签后重开。实际耗时受设备与传输影响，浏览器性能门禁仍待执行。

太阳冠词及融合介词仅在辅音与词干首辅音一致时剥离；太阴前缀拒绝太阳辅音起首。支持 `fix-xemx`、`bid-dar`、`lill-kelb`、`x-xemx`、`d-dar`，拒绝 `ix-ktieb`。增音 `i` 仅在指定咝音辅音群及实存词头匹配时剥离，优先保留实存的 `i...` 词头。提示条区分 `grammar_rule`、`grammar_reference` 与词库来源变位。DMS 排序为数字先于字母、大写先于小写。

## 阅读与导出

八维信息默认平铺；没有折叠面板。每个规范化拼写仍只有一个列表入口，详情中的 `lexeme_analyses` 按来源记录、词性与 `etymology_number` 保留独立形态、词根、IPA、历史词源及义项。例如 `dar` 的房子义及 `djar` 与转动义及 `jdur / midur` 分开呈现；来源本身没有词根时保持空值。`plural_forms` 仅包含有名词性分析支持的词汇复数，不含动词人称、否定或代词连写变位。

提供四种纸张主题、字号、马–中–英 / English–Maltese 切换、Markdown 和 Anki TSV 复制。Anki 的九列是词头、IPA、英文释义、中文释义、含许可与链接的来源、Tier、审核状态、Commons 录音署名链接、分开的子词位分析；Markdown 同样携带来源与待审标签。导出只包含录音文件页链接，不复制录音文件。

快捷键：`/` 聚焦搜索、`↑ / ↓` 切词、`Esc` 关闭发音指南。筛选可叠加；无结果时可切回“全部”与“全部语源”。点击同根词或根标签会清除旧筛选再查询。

筛选包含全部词头、Tier 1 双源核心、Tier 1+2 候选池（16,465）、精选样板（25）、有闪米特词根、罗曼/英语借词、有真人发音，以及各历史词源层。“有闪米特词根”表示实证共时辅音词根，历史词源仍可能待核。

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

本次两阶段重建成功；`python -m unittest discover -s tests -v` 为 **83 项通过、0 失败、0 跳过**，独立 `node tests/phase1_client_checks.mjs` 为 **37 项通过**。

软件测试覆盖真实构建、24,045 守恒、30 桶、字段空值与来源、词形反查、Worker 排序/筛选、音频三分支与失败降级、HTTP 服务及目录边界。`node tests/phase1_client_checks.mjs` 可单独运行客户端行为检查。

最终 Chrome E2E、实际听音、移动端与视觉验收仍按 [RULES.md](RULES.md) 由 Antigravity 执行；本批客户端离线及 SW 检查使用 Node 隔离测试环境，未宣称真机浏览器门禁完成。代码、摘要与测试待 Antigravity 审查并提交；生成数据可按上述命令重建。
