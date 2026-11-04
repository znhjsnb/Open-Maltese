# Open-Malti · 马耳他语认知词典 (Maltese Cognitive Dictionary)

<div align="center">

[![License: MIT](https://img.shields.io/badge/Code_License-MIT-blue.svg)](LICENSE)
[![License: CC BY-SA 4.0](https://img.shields.io/badge/Data_License-CC_BY--SA_4.0-lightgrey.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://www.python.org/)
[![Zero External Dependencies](https://img.shields.io/badge/Dependencies-Standard_Library_Only-orange.svg)]()
[![Quality Gates: 5/5 Passed](https://img.shields.io/badge/Quality_Gates-5%2F5_Passed-success.svg)]()
[![Enriched Lemmas](https://img.shields.io/badge/Enriched_Lemmas-23%2C237%20%2F%2024%2C045-blueviolet.svg)]()
[![Surface Forms](https://img.shields.io/badge/Reverse_Lookup-124%2C488_Forms-informational.svg)]()

**马耳他语（Malti）– 中文（Chinese）– 英语（English）八维认知学习工作台**  
A high-fidelity, eight-dimensional cognitive dictionary for the Maltese language, powered by client-side sharded indexing, PWA offline caching, and deterministic linguistic quality gates.

[功能特色](#-核心特色--features) • [快速启动](#-本机极速启动--quick-start) • [八维架构](#-八维认知架构--8-cognitive-dimensions) • [词库规模](#-词库分层与规模--data-coverage) • [离线技术](#-纯客户端离线架构--offline-architecture) • [开源协议](#-开源许可与署名--license--attribution)

</div>

---

## 🌟 核心特色 · Features

1. **三语认知与精修融合 (Trilingual Cognitive Fusion)**：
   - 涵盖全部 **23,237 个有实证释义的词条**（全库 24,045 词），每个精修词条均具备：**规范小写词性、中文精析、柯林斯式英文长句释义、马耳他语原语释义、双组三语实用搭配、正式+生活双场景角色对话、认知助记与构词分析**。
   - 独创 **精修展示层（Display Senses Layer）**：智能跨源同义去重（消除 Ġabra 与 Kaikki 重复释义），单义词三语合一，多义词独立递进编号，彻底告别拼凑感。

2. **海量词形反查 (124,488 Surface Forms Reverse Lookup)**：
   - 针对马耳他语极度丰富的动词变位、弱辅音变位、破碎复数（Plural Miksur）、太阳字母冠词连音（`ix-xemx → xemx`）及前附着代词/融合介词（`fil-ktieb → ktieb`、`m'għandix → għand`），提供零延迟的即时反查追踪条。

3. **Apple 风格交互工作台 (Apple-Inspired Split-Pane Workbench)**：
   - 左右双栏可拖拽自适应布局、吸顶词头追踪（Pinned Word Header）、义项胶囊速跳（Sense Jump Navigation）；
   - **3D 抽认卡抽屉 (3D Flashcards)**：点击“背词”即可进入沉浸式卡片学习流，支持手势下滑关闭、键盘全快捷键操作；
   - **排版控制浮层 (Typography System)**：白昼、复古羊皮纸、高级灰、深邃夜间四色纸张主题，动态字号与排版密度无缝持久化；
   - **实体化发音药丸**：优先调取 Wikimedia Commons 真人发音，具备马耳他语原生 Web Speech TTS 自动降级与最长字素发音指南。

4. **100% 零后端开支与离线就绪 (Zero Cloud API Cost & PWA Offline)**：
   - 纯静态标准库驱动，客户端轻量内存索引 + Web Worker 毫秒级分片检索；
   - 内置 **IndexedDB 32 项核心资产 SHA-256 校验缓存** 与 Service Worker，一次点击即可持久化离线至本地浏览器，断网亦能秒开检索。

5. **严苛的五道确定性语言学门禁 (5 Deterministic Quality Gates)**：
   - 守恒抽样、Unicode/NFC 规范、词根与词源诚实性（借词绝不伪造闪米特词根）、冠词同化规则与版权出处 100% 自动化代码审计。

---

## 🚀 本机极速启动 · Quick Start

无需安装任何数据库、无需配置收费 API 密钥，仅需 Python 3.10+ 标准库即可秒级启动：

```powershell
# 1. 克隆仓库
git clone https://github.com/znhjsnb/Open-Maltese.git
cd Open-Maltese

# 2. 启动本地零配置服务器（绑定本机 127.0.0.1:8767）
python -X utf8 app/server.py --port 8767
```

打开浏览器访问 **[http://127.0.0.1:8767](http://127.0.0.1:8767)** 即可进入交互工作台！

> **换端口**：执行 `python app/server.py --port 8768`。  
> **PowerShell 编码提示**：Windows 环境下通过管道传递包含特殊字符的文本时，建议先设置：`$OutputEncoding = [Console]::InputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)`。

---

## 📚 八维认知架构 · 8 Cognitive Dimensions

词条详情页彻底摒弃了隐藏信息的“手风琴折叠”，坚持**默认平铺展开、一眼尽览**的沉浸式学习体验：

| 维度编号 | 维度名称 | 包含内容与语言学保障 |
|---|---|---|
| **01** | **词头与发音 (Headword & Phonetics)** | 规范词头、Tier 优先级标牌、阴阳性与个体/集合标注、IPA 国际音标、Commons 真人发音药丸按钮 / TTS 降级 |
| **02** | **构词与词族 (Morphology & Word Family)** | 闪米特三/四辅音词根（`k-t-b`）、格型模式（`Mudell`）、动词变位范式（完成体/未完成体/分词/动名词）、同根派生词族（最多 16 词） |
| **03** | **三语释义 (Trilingual Senses)** | 精修展示义项层（单义词三合一、多义词清晰编号）、中文精析、柯林斯式英文长句释义、马耳他语官方原语释义 |
| **04** | **实用搭配 (Collocations)** | 每词至少 2 组地道三语搭配短语（马耳他语、英语、中文对照） |
| **05** | **双境表达 (Dual Scenarios)** | 正式书面语典范例句 + 日常生活双轮口语角色对话（含发言者身份、口语缩读与标准语对照） |
| **06** | **屈折与附着代词 (Inflection & Clitics)** | 词汇复数、已记录表面形表、定冠词连音规则、实证介词附着代词屈折表（`għandi / għandek...`） |
| **07** | **语用与同源词 (Pragmatics & Cognates)** | 语域标签（口语/正式/罕用/古语）、近义词、反义词、同源词与伪友提示（数据缺省时诚实注明） |
| **08** | **历史词源与助记 (Etymology & Memory Aid)** | 闪米特/西西里罗曼/英语语源层分析、历史传播链去重追溯、图像化/情境化认知记忆助记法 |

---

## 📊 词库分层与规模 · Data Coverage

词库严守实证底线，将 24,045 个词头划分为三层优先级进行科学编纂与管理：

```
全库词位池: 24,045 Lemmas
├── Tier 1 双源核心词 (5,051 词) ────────► Ġabra 与 Kaikki 双权威收录，100% 精修 (已完成)
├── Tier 2 单源精选词 (11,414 词) ───────► 独立有效词根/丰富释义，100% 精修 (已完成)
└── Tier 3 基础词库 (7,580 词)
    ├── 有实证释义 (6,772 词) ────────► 100% 补充三语精修 (已完成)
    └── 底表无英释 (808 词) ──────────► 诚实隔离保持底表原貌 (严禁凭空瞎编)
```

* **总精修词条量**：**23,237 词**（占全部有英文实证词条的 **100.0%**）；
* **表面形反查表**：**124,488 个词形**（含动词变位、虚词连写、介词冠词缩合）；
* **真人发音库**：**597 个** 具备 Wikimedia Commons 录音授权链接的词头。

---

## 🛠️ 纯客户端离线架构 · Offline Architecture

```text
[ 用户浏览器 ]
      │
      ├── 1. Service Worker 拦截静态资源与数据请求
      ├── 2. Web Worker 加载轻量内存索引 (index_lite.json, ~10MB)
      ├── 3. 毫秒级拼写容错搜索 (ASCII-Tolerant, 支持 gh/ie 特殊字素最长匹配)
      ├── 4. 后台懒加载紧凑反查表 (wordforms_lookup.json, ~4.3MB)
      ├── 5. 命中词条时按需请求字母分片 (shards/shard_*.json, 30个分片)
      └── 6. IndexedDB 存储全部 32 项资产 (通过 SHA-256 严格哈希校验)
```

工作台所有计算与搜索均在**用户浏览器端内存**中完成。点击侧边栏的 **“准备离线词库”**，系统会依次下载 2 个索引与 30 个分片，逐字节校验 SHA-256 哈希并回读验证，写入浏览器的 IndexedDB 数据库中，实现断网环境下的完全离线查词。

---

## 🧪 自动化测试与质量门禁 · Quality Gates

项目配置了完整的自动化回归测试集：

```powershell
# 1. 运行五道确定性质量门禁 (Gate 1~5)
python -X utf8 scripts/phase2_quality_gates.py

# 2. 运行 Python 全量单元测试 (133 项全部通过)
python -X utf8 -m unittest discover -s tests -p "test_*.py"

# 3. 运行 Node 客户端逻辑验证 (58 项全部通过)
node tests/phase1_client_checks.mjs

# 4. 运行真实 Chrome CDP 浏览器端到端验收 (PASS 1~12 项通过)
node tests/frontend.browser.mjs
```

---

## 📄 导出能力 · Export

工作台支持将词条一键导出为学习利器：
- **Markdown 格式**：平铺格式化词条全貌，支持直接复制粘贴到 Obsidian、Notion 或 Logseq；
- **Anki TSV 9 列制表符格式**：直接适配专业间隔重复制卡软件（包含词头、音标、英文释义、中文释义、多源出处、Tier 级别、审核状态、Commons 音频链接、独立子词位分析）。

---

## ⚖️ 开源许可与署名 · License & Attribution

本项目采用 **双重开源协议**：

1. **软件与前端代码 (Source Code & Scripts)**：遵循 [MIT License](LICENSE)；
2. **词典数据与文档 (Lexical Data & Documentation)**：遵循 [CC-BY-SA 4.0](LICENSE) (知识共享 署名-相同方式共享 4.0 国际许可协议)。

### 第三方开源语料致谢 (Third-Party Sources Attribution)
- **Ġabra Lexical Database**：遵循 CC BY 3.0，感谢马耳他大学语言学研究所（Institute of Linguistics, University of Malta）及 John J. Camilleri 贡献者团队；
- **Kaikki.org / English Wiktionary**：遵循 CC BY-SA 4.0，保留维基词典词条、词源与屈折表来源；
- **Maltese Verb Inflections**：遵循 MIT License，基于 John J. Camilleri 动词变位基础表；
- **WikiPron**：遵循 Apache 2.0 协议；
- **Wikimedia Commons**：录音文件遵照各自创作者在 Commons 页面标明的授权协议，词典页面均保留原始文件与作者链接。

---

<div align="center">
Made with ❤️ by Open-Lexicon Contributors
</div>
