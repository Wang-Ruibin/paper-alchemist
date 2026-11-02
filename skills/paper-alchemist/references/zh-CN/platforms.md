# Codex 安装与调用

## 安装或升级

用户明确请求安装或升级时，按仓库[安装说明](../../../../docs/zh-CN/INSTALL.md)
准备独立运行环境，并安装用户选择的原生市场版本。保留研究文件、已选画像和无关设置。
私人版包含已审阅指导；公开版需要先蒸馏或导入指导才能写作。

## 调用实际安装副本

通过 Codex 找到实际插件根目录。Windows：

```powershell
& <plugin-root>/runtime/run.ps1 --version
```

macOS/Linux：

```bash
sh <plugin-root>/runtime/run.sh --version
```

将参考中的 `paper-alchemist` 替换为该入口，也可用准备好的 Python 执行
`skills/paper-alchemist/scripts/run.py`。本插件代码优先于其他已安装包。
运行环境在安装步骤准备，普通写作不下载。PDF/OCR 和 LaTeX 属于可选的独立任务。

## 核实可用状态

核对实际安装版本和 `validate-plugin`。内置、导入或自行蒸馏的指导需在研究工作区运行
`validate-profile`。公开版即使安装正确，仍可能需要先提供论文。
新建对话发现更新后的技能，不把运行检查当成当前会话技能发现已刷新。
