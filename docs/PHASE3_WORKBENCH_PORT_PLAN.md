# Open-Malti Phase 3 前端工作台移植与交互重构方案 (PHASE3_WORKBENCH_PORT_PLAN.md · 双模型共识定稿版)

> **对标基准**：`C:\Users\d\Documents\open-melayu`（固定对照提交 `162beb2f8` 的 Apple Design 双栏工作台布局与交互组件）、`C:\Users\d\Documents\dict`（commit `9a6d303`），以及本仓库 `RULES.md`、`docs/MASTER_PLAN_V2.md` §三 & §四.3。  
> **双模型互审状态**：已完成 Codex CLI 只读同行终审（`task-1103`），全量吸收 `[P1]` #1–#4 与 `[P2]` #5–#6 审查意见达成双模型共识。  
> **执行分工**：由 Codex CLI（`-s workspace-write -a never`）主刀完成生产代码重构与客户端/单元测试补充；由 Antigravity 宿主统一运行全量 Python 测试、Node 客户端契约测试与真实无头 Chrome CDP 端到端门禁验收并执行 Git 提交。

---

## 一、 双模型共识：六项强制工程契约（吸收 Codex 审查结论）

### 1. [P1] DOM 选择器、导出函数与偏好状态 100% 向后兼容契约
在移植 `Open-Melayu` / `Open-Lexicon` Apple Design 双栏工作台壳层（`.topbar`、`.workspace`、`#word-sidebar`、`#resizer`、`#content`、`.content-toolbar`、`#toolbar-pinned-word`、`#typography-panel`、`#study`）时，**必须完整保留以下既有 DOM ID、class 与属性契约（严禁改名或删除）**：

| 模块范围 | 必须保留的精确 DOM 选择器 / 属性 / 导出契约 |
| :--- | :--- |
| **顶栏与偏好兼容控件** | `#theme` (`<select>` 含 `white/sepia/grey/night`)、`#font-down`、`#font-up`、`#language-mode`；同步维护 `document.body.dataset.theme`、`document.body.classList.toggle('english-mode', ...)`、`document.documentElement.style.setProperty('--scale', ...)`，并与新增的 `#typography-panel`、`.lang-switch`（`#lang-trilingual` / `#lang-bilingual` / `#lang-en`）及 `#theme-toggle` 共用同一状态源（兼容迁移 `open-malti-preferences`）。 |
| **搜索与导航过滤区** | `#search`、`#clear`、`#search-key`、`#letter-bar`、`#sub-prefix-bar`（`I` 分组下 `.ie-prefix` 置顶）、`#tier-filters`、`#stratum-filters`、`#feature-filters` |
| **状态、列表与分页** | `#result-count`、`#search-time`、`#wordforms-status`、`#headword-list`、`.word-row`、`#previous-page`、`#page-number`、`#next-page`，以及扩展页码跳转控件 `#page-input`、`#page-go`、收藏按钮 `#bookmarks` (`#bookmark-count`)、排序 `#sort-order`、离线按钮 `#offline` |
| **详情卡片与八维容器** | `#entry-card`（内含 `#entry-card h1`、**恰好 8 个 `.dimension` 顶层容器**、全页 **0 个 `<details>`**）、`#morph-trace-banner`、`#pronounce-word`、`#copy-markdown`、`#copy-anki`、`#save` |
| **子词位与对话契约** | `renderAnalyses(analyses)` 必须继续输出以 `<section class="lexeme-analysis">` 为精确分隔符的 HTML 字符串（供 `tests/phase1_client_checks.mjs:160` `html.split('<section class="lexeme-analysis">')` 断言），内部保留 `<h3>`、`.sense .zh` 与 `authored_pedagogical`；06 和 08 维度的子词位分组必须使用独立类名（如 `.inflection-subentry`、`.etymology-subentry`），**严禁复用 `.lexeme-analysis` 类名以免干扰选择器计数**；05 维度对话回合保留 `.dialogue-turn`。 |
| **发音指南与全局弹窗** | `#pronunciation-guide-popover`、`#pronunciation-content`、`#close-pronunciation`、`#toast`、`#inventory-note` |
| **JS 导出接口** | `app.js` 保持导出 `pronunciationGraphemes`, `currentWorkerError`, `renderAnalyses`, `exportText`；`worker.js` 保持导出 `makeSearchEngine`, `exact`, `ascii`, `stripArticle`, `createWorkerHandler`；`db.js` 保持导出 `loadManifest`, `loadJson`, `loadEntry` 并新增导出 `prepareOffline`。 |

### 2. [P1] Worker 协议扩展、固定 60 条分页与流式窗口幂等防重契约
- **保持 60 条/页步长与两阶段启动协议**：
  - 保留 `init → ready → wordforms-ready / wordforms-error` 与 `search → results` 协议，单页大小固定为 **60**（不照搬旧工程的 50）。
- **防止 Stage-2 回放导致流式追加重复插入**：
  - `worker.js` 在 `wordforms-ready` 时会用相同的 `lastSearch`（相同 `requestId` 與 `offset`）重发一次 `results`。
  - 客户端维护按页偏移或 `exact_key` 去重的流式窗口状态：当收到相同 `requestId` 或相同 `offset` 的回放结果时，执行**原地幂等替换（replace in-place）**而非二次追加；当查询词、筛选条件、排序或收藏开关变化时，立即清空流式窗口、重置 `offset = 0` 并递增 `requestId`。
- **Worker 原生支持 `bookmarks` 与 `sort`**：
  - 在 `worker.js` 的 `makeSearchEngine.search(params)` 中正式支持：
    - `bookmarks`：当 `Array.isArray(params.bookmarks)` 时（表示启用了“我的收藏”筛选），在分页切片前按 `new Set(params.bookmarks)` 过滤 `entry.id`（空数组 `[]` 精确返回 `total: 0, results: []`；`null/undefined` 表示未启用收藏筛选）。
    - `sort`：当无搜索词（或同等匹配度）时支持 `'alpha'`（默认 DMS 200 顺序）、`'alpha-desc'`（DMS 200 逆序）、`'tier'`（按 `tier` 1 → 2 → 3 升序，同层保持 DMS 200 顺序）。

### 3. [P1] 06 / 08 维度按 `analysis.id` 严格隔离，彻底废除“已分别列于上方”且零跨词位污染
- **严禁在多子词位词条上输出“各子词位的……已分别列于上方”或“分列如下”**。
- **严禁仅按 POS 粗粒度合并或用顶层聚合字段反填子词位空白**（例如 `dar` 有 5 个子词位，其中 Ġabra 有两个不同词根的动词 `d-j-r`“居住”与 `d-w-r`“转动”，Kaikki 有名词 `dar -> djar` 与动词 `dar -> jdur/midur`； Tier 1 中也有 807 个词条超过 2 个子词位）：
  - **Dimension 06 (`06 · 屈折与附着代词 / inflection & clitics`)**：
    - 单子词位词条：按词性条件渲染（动词展示 `Perfett 3sg.m` / `Imperfett 3sg.m` / `Imperattiv 2sg`，名词/形容词展示 `复数 / plural` 与 `定冠词 L-Artiklu`），并展示分片内已保存的屈折表与 `Pronomi Mehmużin`。
    - 多子词位词条（`lexeme_analyses.length > 1`）：在 06 维度内部按每个 `analysis.id` 渲染 `.inflection-subentry` 卡片（标题标明 `子词位 N · POS · source · source_record_id`），各自独立读取该 `analysis` 自身的 `plural_forms`、`definite_article`、`verb_paradigm`、`attested_forms` 与 `pronomi_mehmuzin`（若某一来源子词位如 `gabra` 在 `abaku` 中未记录屈折形而 `kaikki` 记录了 `abaki` 与 `l-abaku`，则各自如实展示，既直出 `abaki` / `l-abaku`，又绝不把名词 `djar` 与动词 `jdur/midur` 混在同一块中）。
  - **Dimension 08 (`08 · 历史词源 / etymology`)**：
    - 单子词位词条：展示 `.etymology-card`，含语源层 `strata[e.stratum]`、英文词源原文 `e.etymology_text_en`、结构化传播链 `e.source_chain`，以及视觉隔离的 `.cognitive-aid-box`（`学习助记：...` + `authored_pedagogical · phase2_reviewed`）。
    - 多子词位词条（`lexeme_analyses.length > 1`）：在 08 维度内部按每个 `analysis.id` 渲染 `.etymology-subentry`（各自独立读取 `a.stratum`、`a.etymology_text`、`a.etymology_templates`，明确说明“共时词根不代表历史词源”），并在下方展示独立视觉隔离的 `.cognitive-aid-box`（`学习助记：...`）。

### 4. [P1] 离线词库持久化契约 (`prepareOffline`) 与 Service Worker 兼容
- **保持 `sw.js` 现有路由与 `/data/` 离线缓存回退逻辑不变**，确保 `Phase1HTTPTests` 与离线拦截 100% 兼容。
- **在 `db.js` 实现真实的 `prepareOffline(manifest, { onProgress, shouldPause } = {})`**：
  - 按固定 `manifest.version` 依次拉取并校验 SHA-256：`manifest.index_lite`、`manifest.wordforms_lookup` 及全部 30 个 `manifest.shards`（共 32 个数据资产）。
  - 每一项写入 IndexedDB `files` 存储区后，**必须执行同一键名的 IndexedDB 回读校验（read-back verification）**，若IndexedDB 不可用、被拒绝或回读为空，立即抛出明确错误（绝不把仅内存下载成功冒充为“离线词库已就绪”）。
  - 支持 `shouldPause()` 中途暂停并在下次点击时跳过已持久化的资产继续下载。

### 5. [P2] 屈折表节选诚实标注与来源义项译释溯源分离
- **屈折表节选标注**：
  - 当 `a.attested_form_count > (a.attested_forms?.length || 0)` 时，表头说明明确显示：`来源屈折表节选（已展示 ${a.attested_forms.length} / 共 ${a.attested_form_count} 项 · 完整词形可通过搜索反查）`；绝不虚假宣称“已展开完整屈折表”。
- **来源义项与中文译释溯源严格分离**：
  - 在 Dimension 03 渲染 `entry.senses` 时：
    - 若 `s.definition_origin === 'authored_pedagogical'`，标注 `教学编写 · authored_pedagogical · phase2_reviewed`。
    - 若 `s.definition_origin === 'licensed_source'`，英文原义明确标注 `${s.source} · 来源释义 (licensed_source) · ${s.review_status || 'source_attested'}`，而中文/马耳他语译释显式附带 `译释：${s.translation_provenance.definition_origin} · ${s.translation_provenance.review_status}`，绝不让模型翻译顶着 `gabra / kaikki` 原文标签。
- **顶栏音标来源标注**：
  - 顶栏展示去重后的实证 IPA 时，附带对应的 `ipa_source`（如 `/ˈaː.ba.ku/ (kaikki)`）。

### 6. [P2] 动效工程准则 (`emilkowalski/skills`)
- 统一采用弹簧曲线 `--ease: cubic-bezier(0.16, 1, 0.3, 1)`。
- 动画与过渡仅作用于 `transform` 与 `opacity`（严禁 `transition: all` 或对 `width`/`height`/`padding` 做动画；注：`#resizer` 指针拖拽时实时更新 `--sidebar-width` 属于直接操纵布局而非 CSS 过渡动画）。
- 完整支持 `@media (prefers-reduced-motion: reduce)`（禁用 3D 翻转旋转与弹跳动画，降级为透明度切换）。

---

## 二、 自动化门禁与新增真机 Chrome E2E 验收矩阵

1. `python -X utf8 -m unittest discover -s tests -v`：全部 117 项测试 PASS。
2. `node tests/phase1_client_checks.mjs`：原有 37 项 + 新增客户端检查（Worker `bookmarks`/`sort`、Stage-2 回放幂等、`prepareOffline` 回读校验与失败拒绝、06/08 子词位隔离）全部 PASS。
3. `node tests/frontend.browser.mjs`：
   - 原有 **PASS 1–8** 100% 通过。
   - **PASS 9（双源词 `abaku` 与同形词 `dar` 在 06/08 的子词位边界与空行过滤验证）**：
     - 验证 `abaku` 的 06 维度包含 `abaki` 与 `l-abaku`，08 维度包含 `Borrowed from Italian abaco.` 与 `学习助记：`，全卡片不含“列于上方”或“分列如下”，且不渲染空白的动词专属行。
     - 验证 `dar` 在 06 维度的 `.inflection-subentry` 中名词块含 `djar` 且不含 `jdur/midur`，动词块含 `jdur/midur` 且不含 `djar`；08 维度同样按子词位隔离。
   - **PASS 10（旧工程工作台壳层、`#resizer` 拖拽持久化、吸顶 `#toolbar-pinned-word`、义项速跳 `.sense-chip` 与沉浸模式 `#focus`）**。
   - **PASS 11（`#typography-panel` 阅读排版浮层与 `#theme` / `#font-up` / `#font-down` / `#language-mode` / `.lang-switch` 双向同步及重载持久化）**。
   - **PASS 12（`#study` 3D 抽认卡抽屉翻转与下滑关闭、`#save` + `#bookmarks` 收藏过滤联动、`#offline` 32 项资产 IndexedDB 持久准备验证）**。
