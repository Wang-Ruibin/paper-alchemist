# 研究与写作工作流

[English](../research-workflow.md)

## 选择进入阶段

按用户请求进入规划、文献研究、写作、审稿、修订或定稿。完整流程连接这些阶段；只写一节不需要重新做研究计划或组织审稿小组。已有稿件和审稿信可以直接进入审稿或修订。复用已确认的决定，继续已获授权的工作；只就缺失事实、实质研究选择或超出授权的外部操作询问用户。

| 请求 | 有用的交付物 | 下一步阅读 |
| --- | --- | --- |
| 发展选题或研究计划 | 研究问题、明确范围、方法选择及所需证据 | 下文的规划部分 |
| 查找或比较文献 | 检索记录及论断与来源的证据矩阵 | [literature-evidence.md](literature-evidence.md) |
| 写一节或整篇论文 | 各模块 brief 及有事实依据的学术正文 | [generation.md](../generation.md) |
| 评阅稿件 | 定位明确、有证据及具体改法的问题 | [review-revision.md](review-revision.md) |
| 回复审稿人 | 意见与修改对应关系及有依据的回复 | [review-revision.md](review-revision.md) |
| 准备最终文件 | 当前事实审阅、文献核对及已检查的输出 | 下文的定稿部分 |

研究规划、文献工作和评阅现有稿件不要求先完成文风画像。使用语料指导写作时，仍须通过已有的画像就绪和分模块生成检查。内置语料的领域范围不等于适用于所有学科的证据。用于其他学科时，识别可迁移的写作模式及缺口；需要不同指导时，使用用户相关领域的画像，或蒸馏获授权的参考论文。

## 从已有研究材料开始规划

先读用户提供的笔记、草稿、表格和参考文献，再补问。形成简短研究简报：问题、范围、拟议贡献、现有证据、可选方法，以及能够区分不同解释的下一项证据。方案保持“拟议”身份，只有研究材料支持的结果才写成已观察事实。保留疑点和相反发现，不把期望中的贡献当成已证明结论。

按研究类型组织证据计划。实证研究可能需要数据、比较对象、指标与不确定性；理论研究需要定义、假设及待证明事项；文献综合需要检索与筛选方案。不对所有研究问题强加求解器基准、统计检验或实验。结合问题与已有证据说明实质方法取舍，不编造已执行工作。

拟提纲时，把每项预期贡献对应到支持它的章节与证据；缺口记在正文之外。全文写作请求通常已经授权建立并采用合理提纲，只有不同结构会改变研究解释时才需要用户决定。可选的用户自有写作样本可以辅助语气和术语，已审阅语料提供群体层面的修辞模式；两者均不提供研究事实。

## 按任务需要保留可续接记录

长项目或明确审计任务可以在用户授权的路径保存研究简报、来源、当前研究事实、稿件版本、审稿及下一项待解决工作。操作记录与论文正文分开。结构化记录由 Agent 建立，不让研究者手改 schema。未获文件写入授权时，在对话中返回请求的内容。

续接时先读实际文件并比对记录中的哈希，再复用判断。需要解释审稿意见时保留当时受审版本。事实、来源或表述变化后，复核受影响的论断。哈希只能识别变化，不能使随机模型输出可逐字复现，也不能证明实验实际执行过。

## 在本地检查证据与修订绑定

需要持久溯源时，使用可选的 Agent 编写的[工作流记录](../../assets/workflow-record.example.yaml)。它独立于现有语料画像记录及[稿件语义审阅](draft-audit.md)。运行：

```bash
paper-alchemist check-workflow workflow.yaml --draft paper.md --context paper-context.yaml --workspace . --stage review --out workflow.check.json
paper-alchemist check-workflow workflow.yaml --draft paper.md --context paper-context.yaml --workspace . --stage final --out workflow.final.json
```

未传 `--out` 时命令只读。它不获取来源、不调用模型、不启动实验，也不修改文风库；拒绝用报告覆盖输入文件。退出码为零仅表示已登记的绑定满足所选阶段的检查，不代表论文通过验收。

| 字段 | 约定 |
| --- | --- |
| `schema_version` | 整数 `1` |
| `draft_sha256`、`context_sha256` | 当前哈希，口径与 `audit-draft` 相同；诊断会输出两者 |
| `artifacts` | 唯一 `id`、相对工作区的 `path`、原始字节 `sha256` 及 `kind` 的列表；类型为 `study`、`literature`、`review` 或 `draft` |
| `claims` | 非空列表，每条有唯一 `id`、精确 `start`/`end`/`text`、`context_paths`、`assessment`（`supported` 或 `unresolved`）、`rationale` 及可选 `evidence` |
| `evidence` | 来源文件 ID、实际读过的精确 `quote`、人可读的 `locator`、`relation`（`supports`、`contradicts`、`insufficient`）、`rationale` 及可选已授权 `citation_key` |
| `reviews` | 可选的唯一审稿 ID、报告 `artifact_id`、保留的受审稿件 `draft_artifact_id`、实际 `reviewer`/`reviewer_kind`，以及含唯一 `id`、原始 `text` 和 `severity`（`major` 或 `minor`）的 `comments` |
| `resolutions` | 可选的唯一 `comment_id`、`action`（`revised`、`rebutted`、`deferred`）及 `rationale`；闭环项还需当前稿件/事实哈希、`verified_by` 和 `verifier_kind` |

位置从零开始，以按通用换行方式读取的 UTF-8 稿件的 Unicode 码点为单位，结束位置不包含在片段内。稿件哈希覆盖这样解码后的文本；事实哈希覆盖解析结果按键排序、紧凑分隔且不转义 Unicode 的规范 JSON。文件哈希覆盖原始字节，包括 CRLF。证据引文采用通用换行后的 UTF-8 文本。PDF 应在阅读笔记保留原文件哈希、印刷页码/章节，并登记已检查的文本笔记；本命令不查看 PDF 原页，也不认证笔记内容。

事实路径可以指向已有内容的 `research` 或 `citations` 字段，包括列表索引。写作材料的提供状态不能支持科研论断。标为已支持的被引论断需要 `literature` 文件和相同引用键，仅有参考文献条目不足以通过。明确标为 `unresolved` 的论断在审稿阶段可保留已有引用键及证据缺口，但会阻止最终交接。逐个登记被引分句：每次识别到的引用标记都须落在已登记片段内，包括同一个键的多次使用。纯数字或作者年份引用需要明确键映射，并通过 `audit-draft` 进行语义核对；本助手不将它们解析为引用键。

`revised` 项必须指向当前稿件的精确片段。删除论断时，以周围修改后的段落为锚点并说明删除了什么。`rebutted` 项需要支持回复的当前事实路径或来源证据。未填或 `deferred` 的意见保持待处理。审稿阶段把未解决论断/意见列为警告，允许继续评阅；最终阶段会阻止通过。文件过期、记录类型错误或证据绑定断裂在两个阶段都失败。稿件或事实变化后，即使已刷新记录顶层哈希，也必须重新核实旧的闭环判断。

本工具只检查已登记片段及意见。完整提取、来源真实性、语义蕴含和审稿判断是否正确仍需实际阅读。登记 Agent 身份不等于已认证的人类或独立审稿人。不得把 `traceability_ready` 当成质量评分、同行评审结论或投稿保证。

## 完成请求的交付物

统一摘要与正文、论断强度、符号、数值、文献、图和表。对当前稿件执行已有 `audit-draft` 流程及当前语义审阅，`check-workflow` 不取代它。若修订记录在任务范围内，也执行其最终检查。所需格式及工具支持时，编译并查看渲染页面。如实说明未执行检查，不虚构接收结论，也不把操作说明塞进正文。定稿请求本身不授权向期刊投稿、联系审稿人或运行实验。

## 使用宿主已有能力

| 能力 | 行为 |
| --- | --- |
| Codex 原生插件 | 默认安装与发现方式，使用内置运行时 |
| 其他支持技能的宿主 | 可复用工作流文本及本地 Python CLI；尚未验证其安装和编排 |
| 无浏览能力 | 使用已提供来源，未获取文献及检索覆盖保持待确认 |
| 无委派能力 | 同一 Agent 顺序进行不同角度阅读，并如实说明 |
| 无文档渲染器 | 交付可支持的请求文本格式，并说明缺少视觉检查 |

不要求特定模型、付费文献服务、额外 LLM API、Claude 命令、Hook 或自动启动子 Agent。工具使用遵循宿主权限和用户任务范围。

## 设计参考

工作流设计参考了 Cheng-I Wu 的 [Academic Research Skills](https://github.com/Imbad0202/academic-research-skills)，于 2026-11-08 核对提交 `6d9388674de1ad0437ad95db3d52f92b92204d84`：包括其[阶段架构](https://github.com/Imbad0202/academic-research-skills/blob/6d9388674de1ad0437ad95db3d52f92b92204d84/docs/ARCHITECTURE.md)、[交接约定](https://github.com/Imbad0202/academic-research-skills/blob/6d9388674de1ad0437ad95db3d52f92b92204d84/shared/handoff_schemas.md)及[审稿流程](https://github.com/Imbad0202/academic-research-skills/blob/6d9388674de1ad0437ad95db3d52f92b92204d84/academic-paper-reviewer/SKILL.md)。该项目使用 [CC BY-NC 4.0](https://github.com/Imbad0202/academic-research-skills/blob/6d9388674de1ad0437ad95db3d52f92b92204d84/LICENSE)。
这里的实现与指令独立编写，不包含上游代码或提示词原文。不采用其逐阶段确认、固定 Agent 团队、模型路由和审稿评分。Paper Alchemist 原有事实边界与语料记录继续作为本插件的依据。
