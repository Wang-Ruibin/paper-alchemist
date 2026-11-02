# 复用已审阅画像

[English](../portable.md)

安装后的插件已经包含 95 篇已审阅论文的写作指导，新用户可直接据此写作；单独
导入画像是可选操作。此流程用于分享自定义画像，或已加入新论文的完整资料。

## 导出已完成画像

用户希望在另一个项目写作，或将已审阅画像移到另一台电脑时，使用此流程。
根据请求确定路径，不让用户手动组装内部文件。只有 `validate-profile` 确认
可用于生成后才导出。

```bash
paper-alchemist export-profile --profile <name> --workspace <source-project> --terminology-registry <registry.json> --out <profile.zip>
```

导出包包含章节指导、整合画像、语义观察、阅读范围、来源标识与校验和，以及可选的
术语表和来源目录。不包含参考论文、抽取原文、当前研究上下文、初稿或凭据。
没有术语表时省略 `--terminology-registry`；已导入画像再次导出时保留附带术语表。
已存在的输出包不会被覆盖。

整体资料启用了新增画像时，同一命令一起导出基础和全部已审阅新增指导。未完成的
新增画像会阻止导出，不会被静默遗漏。导出包保留各层的已审阅来源绑定，移除其
清单中的本机来源位置；在接收项目中显式重新连接实时目录。

## 在另一个项目导入并写作

```bash
paper-alchemist import-profile <profile.zip> --workspace <writing-project>
paper-alchemist validate-profile --profile <name> --workspace <writing-project>
```

导入前核对文件哈希、来源章节绑定、证据指纹和语义综合完成状态。同名画像或证据
缓存已存在时予以保留。随后在接收项目中正常准备章节提示；除非显式指定其他术语表，
默认使用导入包附带的术语表。单章节和全文写作仍遵循正常流程。

导入含新增指导的完整资料时，先验证所有画像，再开始安装。目标已有同名画像或
缓存时拒绝覆盖并保留现有状态。在新项目中，导入的整体资料会成为选定写作画像，
包含新增模块指导及术语。

导入画像是已审阅快照，其来源状态保存在操作记录中，不进入论文。仅复用写作指导
不需要复制参考论文；实时检查可能发现原目录不可用，但不会把其中论文视作已删除。

## 继续增量蒸馏

用户只提供新增论文时，按 [incremental.md](incremental.md) 对整体资料使用
`distill --extend`，无需原始论文即可保留已审阅指导。重新连接导入的新增目录时，
选择其既有层并显式迁移，避免重复增加来源影响。

更新前检查已保存的来源目录：

```bash
paper-alchemist scan-corpus --profile <name> --workspace <writing-project>
```

论文仍在原位置时，使用已获授权的正常 `distill --update` 流程。插件重建本地抽取
缓存，保留论文与章节内容匹配的观察，仅对变化证据安排语义工作。新增论文仍须
阅读来源并更新受影响综合；导入指导不会自动完成新增论文蒸馏。

语料移到其他位置时，先检查用户提供的新目录，再重新绑定：

```bash
paper-alchemist scan-corpus --profile <name> --workspace <writing-project> --source <paper-folder>
paper-alchemist distill <paper-folder> --profile <name> --workspace <writing-project> --update --rebind-source
```

保留已保存的抽取与选择策略。重新绑定只迁移一个跟踪目录，不合并无关语料。
实际抽取后，校验使用恢复的章节正文，而非快照哈希。保留有效旧观察，完成待审阅
内容与综合，再按需整合。导入快照已经整合；重新连接来源证据前，不重写其整合文件。

## 准确理解校验结果

校验和证明资产完整性与来源绑定的可复查性，不证明原实验真实、不等于重新独立阅读
PDF，也不代表生成论文通过质量验收。修改导入画像或观察会使快照失效，不能仅改
校验和来恢复状态，应采用有来源支持的更新与审阅流程。
