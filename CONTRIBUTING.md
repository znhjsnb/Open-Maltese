# 贡献指南 (Contributing to Open-Malti)

欢迎参与 **Open-Malti（马耳他语–中文–英语三语认知词典）** 的建设与完善！无论是订正义项、增补真人录音、完善语源考证还是改进前端工作台，我们都非常期待您的贡献。

---

## 一、 核心编纂准则 (Editorial Principles)

1. **实证性与诚实原则**：
   - 严禁脑补或虚构未经实证的闪米特三/四辅音词根（`Għerq`）。罗曼与英语借词一律标注为借词整词记忆与同化形态，不捏造辅音词根；
   - 凡实证语料缺失的维度（例如某些借词无附着代词、无破碎复数、无历史传播链记录），字段应当为空，严禁伪造内容。
2. **三语认知对齐**：
   - 中文精释注重概念清晰与现代汉语自然表达；
   - 英文长释义采纳柯林斯/朗文式完整句子定义风格；
   - 马耳他语原语释义严格遵守马耳他国家语言委员会（Il-Kunsill Nazzjonali tal-Ilsien Malti）规范拼写。
3. **分层隔离与同形异义词保护**：
   - 像 `dar`（房屋 vs 转向）这样具备不同词根、词性的同形异义词，必须在各自独立子词位（`lexeme_analyses`）中呈现，严禁将不同词位的形态、复数或词源混为一谈。

---

## 二、 本地开发与测试流程 (Local Development & Verification)

### 1. 环境准备
- Python 3.10+（构建与服务器仅使用标准库，零外部依赖）
- Node.js 18+（用于自动化客户端与端到端测试，可选）

### 2. 启动本地服务
```powershell
# 启动本地零配置静态服务器（默认端口 8767）
python -X utf8 app/server.py --port 8767
```
打开浏览器访问 `http://127.0.0.1:8767/`。

### 3. 执行五道质量门禁与回归测试
在提交 Pull Request 前，请确保所有自动化门禁全部通过：
```powershell
# 运行五道确定性质量门禁（Unicode/NFC、词源诚实性、冠词与代词、许可出处、守恒抽样）
python -X utf8 scripts/phase2_quality_gates.py

# 运行 Python 单元测试全集（133 项）
python -X utf8 -m unittest discover -s tests -p "test_*.py"

# 运行客户端 Node 逻辑检查（58 项）
node tests/phase1_client_checks.mjs
```

---

## 三、 Pull Request 规范

1. **原子提交**：每个 PR 聚焦单一主题（例如修正某一组词条的释义、修复某项排版样式、优化分词逻辑）；
2. **保留数据出处**：若增补或修正语言学字段，请注明参考的一手语料或出版文献（如 *Ġabra*, *Aquilina Dictionary*, *Kunsill tal-Malti* 规范文件）；
3. **保持测试绿灯**：所有 PR 必须 100% 通过现有质量门禁，且不得降低测试覆盖率。
