<div align="center">

# Paper Alchemist

### 蒸馏优秀论文的写法，用可信证据完成写作。

一个支持中英文论文写作规律学习与事实约束生成的跨 Agent Skill。

[![CI](https://github.com/Wang-Ruibin/paper-alchemist/actions/workflows/ci.yml/badge.svg)](https://github.com/Wang-Ruibin/paper-alchemist/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/Wang-Ruibin/paper-alchemist)](https://github.com/Wang-Ruibin/paper-alchemist/releases)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-compatible-6f42c1)](https://agentskills.io/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[English](README.md) · **简体中文**

</div>

## 它能帮你做什么

Paper Alchemist 从参考论文中学习不同章节的组织方式、论证顺序和表达习惯，再把这些规律用于你的论文写作。

- 分别学习摘要、引言、文献综述、问题定义、方法、实验设置、结果分析和结论的写法；
- 单独生成或修改某一章节，也可以组合生成全文初稿；
- 同时利用中英文论文的写作经验，并以目标语言的表达习惯为主；
- 只使用你确认过的研究事实和引用，不从参考论文中照搬内容；
- 在本地处理论文和研究材料，不调用额外的 LLM API。

参考论文负责提供“怎样写”的经验；你的草稿、实验记录和回答负责提供“写什么”的事实。

## 支持的 Agent

Paper Alchemist 支持 Codex、Claude Code、OpenCode、Hermes、Pi Agent 和 Kimi Code。安装后直接在对话中说明想蒸馏哪些论文或想生成哪个章节即可。

## 从安装到写作

整个过程都可以通过和 Agent 对话完成。你不需要学习命令，也不需要手工准备配置文件。

### 1. 让 Agent 安装

把下面这段话发给 Codex、Claude Code、OpenCode、Hermes、Pi Agent 或 Kimi Code：

```text
请从 https://github.com/Wang-Ruibin/paper-alchemist 安装 Paper Alchemist，
并为当前 Agent 做用户级配置。请检查运行环境、完成安装并确认以后新会话仍可使用。
不要覆盖已有安装；如果需要安装或升级 Python、PDF 工具或 OCR 组件，先征得我的同意。
完成后告诉我是否需要重新打开会话。
```

如果只想在当前研究项目中使用，把“用户级配置”改成“项目级配置”。

### 2. 让 Agent 蒸馏参考论文

把参考论文放进一个文件夹，例如 `./papers/`，然后说：

```text
请使用 Paper Alchemist 学习 ./papers 中论文的写作方式，
并把这套论文画像命名为 routing-literature。
请完成全部章节的学习和检查，不要只处理文件内容就停下。
保护好我的论文和研究材料，不要把它们提交到版本控制。
完成后告诉我这套画像是否已经可以用于写作、哪些论文被采用，以及有哪些限制。
```

这个过程可能需要一些时间。Agent 会继续完成论文读取、章节分析和写作规律归纳；只有遇到需要你决定的问题时才会停下来询问。

### 3. 等待画像准备完成

画像可用后，你会看到清楚的结果说明，例如：

> **`routing-literature` 画像已经准备好，可以开始写作。** 本次采用了 18 篇论文；另有 2 篇无法读取，未参与学习。结果分析部分的英文参考较少，生成时会更加谨慎。

如果 Agent 只告诉你“论文已经读取”或“还有章节没有完成”，回复“请继续完成这套画像，准备好后再告诉我”即可。

### 4. 开始写你的论文

告诉 Agent 你想先写哪个部分，并提供现有研究材料的位置。材料可以是论文草稿、研究笔记、实验表格、结果文件或 BibTeX 文献库。

```text
请使用 routing-literature 画像帮我写中文文献综述。
我的研究材料在 ./draft/，实验结果在 ./results/，参考文献在 ./references.bib。
请先阅读这些材料，整理出可以使用的研究事实和引用；有不清楚或缺少的内容时，
分几次向我提问。确认信息无误后再生成文献综述，不要补写未经确认的事实。
```

如果材料还没有整理好，也可以直接说：

```text
请使用 routing-literature 画像帮我写中文摘要。
我的研究材料还没有整理好，请一次问我几个容易回答的问题，
逐步确认研究问题、方法、贡献和结果，然后再生成摘要。
```

Agent 会先整理并确认当前章节真正需要的信息，再开始写作。

## 按章节生成，也可以生成全文

每个章节会使用与它对应的写作画像。你可以只完成当前需要的部分，之后再继续其他章节。

| 你要写的内容 | Agent 会重点确认 |
|---|---|
| 摘要 | 研究问题、现有不足、方法、贡献和主要结果 |
| 引言 | 研究背景、具体问题、研究空白和贡献 |
| 文献综述 | 研究空白、文献分组、比较关系和可用引用 |
| 问题定义 | 研究对象、假设、决策、约束和目标 |
| 方法 | 方法目的、整体思路、组成部分和设计理由 |
| 实验设置 | 数据集或算例、基线、指标、参数、硬件和随机种子 |
| 结果分析 | 对比对象、准确数值、统计证据、解释和启示 |
| 结论 | 已验证的发现、贡献、局限和可支持的后续方向 |

只生成一个部分时，直接说“先写摘要”或“只生成文献综述”。已经写过的章节也可以交给 Agent 按画像修改。

需要全文初稿时，可以说：

```text
请使用 routing-literature 画像和我提供的研究材料生成一份完整论文初稿。
先确认全文需要的事实和引用，再分别生成引言、文献综述、问题定义、方法、
实验设置、结果分析、结论和摘要。保持术语、贡献表述、数字和引用前后一致，
最后合并成一个 LaTeX 文件保存到 ./draft/paper.tex。
缺少信息时先向我提问，不要自行补全研究事实。
```

Agent 会按章节分别应用对应画像，再把各部分组合起来；摘要通常最后生成，以便与正文保持一致。

## 支持的材料

参考论文可以使用 PDF、LaTeX、DOCX、Markdown 或纯文本。普通 PDF 可以直接读取；扫描版或文字很少的 PDF 可能需要 OCR，Agent 会在安装额外组件前询问你。

你的研究材料不必采用固定格式。可以直接提供文件路径，也可以在对话中回答问题。数值、单位、数据集名称、基线、实验条件和引用必须来自这些材料或你的明确确认。

## 你会得到什么

- 一套可重复使用的论文画像，按章节保存中英文写作规律；
- 一份简明的蒸馏结果，说明采用和排除的论文以及已知限制；
- 按需生成的单个章节、多个章节或完整论文初稿；
- 当参考材料不足或研究事实缺失时，清楚的提示和待补信息。

## 写作边界

- 参考论文只用于学习组织与表达方式，不作为你的研究证据；
- 不模仿单一作者，不保存或复用论文中的长句；
- 不编造贡献、方法、数据集、基线、参数、结果、显著性、局限或引用；
- 图表可以用于学习如何介绍和分析视觉证据，但不会从图像中猜测未标注数值；
- 生成结果是需要作者审阅和修改的论文初稿，不替代学术判断与事实核验。

## 遇到问题

| 情况 | 可以怎么做 |
|---|---|
| Agent 无法读取扫描版 PDF | 同意安装 OCR 后重试，或换用带文本层的 PDF |
| 有论文未参与蒸馏 | 让 Agent 说明无法读取或章节不足的具体原因 |
| 画像迟迟没有准备好 | 让 Agent 继续未完成的章节，并只在需要你处理时停下 |
| 生成前反复询问信息 | 提供草稿、实验结果和文献库路径，或逐项确认缺失事实 |
| 生成内容缺少某个结果 | 先确认该结果及准确数值，再让 Agent 重新生成对应章节 |

## 开源协议

MIT © 2026 Wang-Ruibin。详见 [LICENSE](LICENSE)。

---

<div align="center">

如果 Paper Alchemist 对你的研究写作有帮助，欢迎随手送它一颗 Star，让这位小炼金术士开心一下。✨

[![Star History Chart](https://api.star-history.com/svg?repos=Wang-Ruibin/paper-alchemist&type=Date)](https://star-history.com/#Wang-Ruibin/paper-alchemist&Date)

</div>
