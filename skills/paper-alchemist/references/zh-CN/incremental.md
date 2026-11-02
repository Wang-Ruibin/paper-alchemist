# 论文列表与增量蒸馏

[English](../incremental.md)

## 显示已蒸馏论文

在新的写作工作区，`list-papers` 自动使用随插件提供的 95 篇已审阅论文指导；
已有选定画像优先。查看和使用内置指导都不需要原始 PDF。由 Agent 选择合适画像，
不要求用户配置内部字段。

在持有画像的工作区运行插件的 `list-papers --profile <name>`。它会检查已登记
目录的内容哈希，显示各篇论文状态。`--json` 提供来源身份、阅读范围、已识别／
未识别模块及单项观察记录。只有无法实时访问或明确不需要时才使用 `--cached`，
并说明没有检查文件变化。

将列表翻译为用户使用的语言，区分待审阅论文、已审阅已识别章节但等待画像综合的
论文，以及已经纳入完整整合画像的论文。提取成功不等于完成蒸馏；已识别章节审阅
完成不等于逐行审核了整篇 PDF，结构就绪也不等于生成文章质量已经通过验证。

## 检查已登记目录

开始语料维护请求时，以及写作任务复用画像之前，运行一次：

```bash
paper-alchemist scan-corpus --profile <name>
```

这个只读扫描比较内容哈希，报告新增、修改、改名、删除和完全相同的副本，不进行
提取或语义审阅。无法访问目录时报告“不可访问”，不得把其中论文视为已删除。
冻结评测画像保持原来的来源选择，范围外文件不会自动进入训练集。

如果用户请求了增量蒸馏，或已授权持续升级语料，则在已有授权内继续完成。如果
用户只要求查看／检查论文，或使用现有画像写作，则说明变化，在修改画像前取得
缺少的更新指示。已授权的更新过程中不得反复询问。扫描在调用插件时执行，不是
无人值守的文件监听器或后台语言模型服务。

## 核对 PDF 的文本顺序

如果提取后的段落混合了两栏文字，比较自动顺序与内容流顺序，并对照原始页面：

```bash
paper-alchemist compare-pdf-text <paper.pdf>
```

这会生成带内容哈希的私有候选文本和比较记录，不修改画像、不选择优先顺序，也不
进行语义审阅。根据原文段落是否连贯来选择，不能按候选文本更长或识别标题更多来
判断。图中文字和错位浮动块仍可能需要来源绑定的章节边界。

联系信息或浮动块打断了一个词时，对照原页核实词片段，并在已审阅章节映射的对应
边界使用 `join: word`。它连接已有的字母片段，不插入空格，不猜测缺失字母，也不
删除连字符。默认分段及 `join: continuation` 仍保留原有分隔符。通过
`distill --update --section-map` 应用映射，重新阅读受影响章节，再用
`record-observations` 记录新哈希；未改变的观察继续复用，受影响观察的上一份有效
记录保留在历史中。由 Agent 建立映射，不要求用户手工编辑。

由 Agent 根据比较结果中的实际来源哈希建立审阅文件，不要求用户配置 JSON。
格式如下：

```json
{
  "schema_version": 1,
  "documents": [{
    "source": "paper.pdf",
    "source_sha256": "<actual source SHA-256 from the comparison>",
    "pdf_text_order": "raw",
    "reviewer_kind": "agent",
    "reviewer": "<identified reviewer>",
    "review_status": "complete",
    "rationale": "Original PDF columns checked; content-stream order keeps the research paragraphs separate."
  }]
}
```

`source` 是规范来源论文相对已登记目录的路径。`auto` 保持自动提取；`raw` 要求
Poppler 的内容流提取，无法获得该顺序时会明确失败。应用审阅后的选择：

```bash
paper-alchemist distill <registered-folder> --profile <name> --update --pdf-order-map <reviewed-pdf-order.json>
```

只改变明确指定的选择。后续更新对相同来源字节沿用选择，包括改名；来源字节变化
会清除旧偏好，恢复自动提取，等待再次核对。明确传入过时哈希、未选入的来源或非
规范副本会被拒绝。顺序改变时只重抽取该篇，使受影响观察失效并保留上一份有效
审阅，其他当前观察仍可复用。便携画像携带此选择以便连接原文后重抽取。完成文本
顺序审阅不等于完成章节观察，也不等于写作画像已经就绪。

## 仅新增论文并保留已审阅指导

使用内置语料，或原始论文不可用的导入画像时，保留已审阅基础，单独蒸馏用户的新增目录：

```bash
paper-alchemist distill <only-new-paper-folder> --profile <parent-name> --extend
paper-alchemist review-plan --profile <parent-name>
```

插件与基础语料及其他新增资料比较文件哈希，只提取新增材料，不重建原有抽取缓存。
完全相同的副本不增加证据。按照队列每一项的 `profile` 记录观察、综合章节并运行
`integrate`。只有全部启用的新增画像都完成审阅和整合，整体才可用于写作。章节提示
随后包含相应新增模块、合并后的语言来源数量和有来源范围的术语。仅一篇论文提供的
证据仍属低置信度，不会自动推翻广泛支持的写作规律。

后续调用检查各个已登记的新增目录。目录内容变化时再次运行 `distill --extend`，
保留既有抽取策略和仍匹配的观察。目录暂时不可访问时保留已审阅指导；确认删除的
论文退出启用的新增证据，原基础保持不变。即使目录暂时没有独有论文，仍会在后续
调用时检查新文件。`--cached` 不访问实时目录。这些检查按调用执行，没有后台常驻服务。

换电脑后重新连接新增目录时，由 Agent 识别已有层、检查新位置，再执行：

```bash
paper-alchemist distill <relocated-added-folder> --profile <parent-name> --extend --addition-profile <added-profile> --rebind-source
```

不得用稀疏的新增目录通过 `--update` 替换已审阅基础。通过整体的
[可移植导出](portable.md) 一起分享基础及全部启用的已审阅新增指导。当前研究事实与
初稿保持独立。

## 更新持有原始来源的自定义语料

新增论文放在画像已经登记的论文目录及其子目录内。从现有清单推断路径，不要求
用户编辑配置。运行：

```bash
paper-alchemist distill <registered-folder> --profile <name> --update
paper-alchemist review-plan --profile <name>
```

除非明确更改，更新沿用语言、OCR、最低文本量和评测来源选择设置。未变内容复用
提取结果和仍有效的观察；完全相同的副本会列出，但不会增加语料权重。改名复用
内容证据并更新来源标签，受影响的画像标签仍需要更新。修改后的论文获得新身份
并重新审阅；删除论文退出当前证据集，每篇来源／模块／语言保留一份之前审阅
记录在私有观察历史中。插件不会修改或删除源论文。

`review-plan` 列出待审、失效或缺失的来源章节观察，以及需要综合的模块画像。
只补齐这些观察，综合更新语料时参考仍有效的旧观察。模板缺失时，重新运行
`distill --update` 恢复。阅读实际章节，布局含糊时检查 PDF 页面；撰写五项语义
观察并如实记录阅读范围。通过插件保存 Agent 撰写的 JSON 标注：

```bash
paper-alchemist record-observations --profile <name> --annotations <agent-authored.json> --reviewer <reviewer-name>
```

每项标注包含当前已纳入的来源、语言、模块和精确章节哈希，以及 `reading_scope`、
`rhetorical_moves`、`language_and_stance`、`evidence_introduction`、
`transferable_pattern`、`risks_and_exceptions`。可选来源哈希也必须匹配。命令
先校验整批标注，再保存审阅者和时间，不会生成语义发现。阅读和综合方法见
[workflow.md](../workflow.md)。
`reading_scope` 可以是文字说明，也可以记录当前章节长度、有序半开字符区间、
实际覆盖量、模式和解释。只覆盖部分区间时，不得标为完整章节审阅。

即使论文字节没有变化，修订已有观察的解释或阅读范围，也会使对应的已完成模块
综合与整合画像失效。替换观察或重新绑定章节边界前，保留上一份有效审阅记录；
连续修改尚未重新审阅的边界，不会覆盖这份有效记录。同一审阅者重复提交相同
观察，会保留原观察文件及其时间戳。

重新审阅并综合受影响模块，保留有用的旧指导，说明新增变化。零源论文语言的辅助
指导也需要在源语言证据变化后更新。原先缺失的语言新增证据，或某语言的最后一份
证据被移除时，也要更新关于其证据可用性的指导；另一语言仍有效的观察可继续复用。
随后通过插件整合、验证，检查论文列表，并
执行对应写作回归：

```bash
paper-alchemist integrate --profile <name>
paper-alchemist validate-profile --profile <name>
paper-alchemist list-papers --profile <name>
```

来源观察、综合或整合仍待完成时，不得报告蒸馏已完成。说明论文变化、保留的旧
工作、更新的章节，以及剩余来源问题和写作测试限制。

## 目录迁移与已审阅边界

`distill --update` 传入不同目录不会合并语料，默认拒绝。先用
`scan-corpus --source <new-folder>` 检查可能的目录迁移。只有用户明确要求迁移，
且核对同内容／缺失／新增文件后，才传入 `--rebind-source`。不同目录需要明确
安排共同语料目录或分别建立画像；不得用新目录默默替换原来的语料。

保存的章节映射如果来源或原文变化，就失效、被报告并退出当前使用。撰写新观察
前检查恢复后的边界；明确传入过时映射时拒绝使用。局部角色修正可按映射契约
只替换选定模块，保留未受影响自动模块的精确文本。列明所有改变或清除的角色，
重新审阅发生变化的证据；论文字节未变不表示新的边界解释自动有效。
哈希和私有更新历史支持复现，
不会执行语义蒸馏，也不能证明已经阅读来源段落。
