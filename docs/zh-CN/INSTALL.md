# 安装 Paper Alchemist

本文供 Codex 执行用户明确请求的安装或升级。保留研究文件、画像选择和无关 Codex 设置。

## 检查权限并选择版本

阅读 README 和 `.agents/plugins/marketplace.json`。私人
`paper-alchemist-private` 市场包含已审阅指导；公开 `paper-alchemist`
市场是空白版，不得相互替代。私人仓库使用者须先接受邀请并具备 GitHub 访问权限。
复用已有认证，不要求用户在聊天中粘贴令牌；权限缺失时说明具体登录步骤。

检查 `codex plugin --help`。缺少命令时，帮助用户更新支持的客户端，再确认成功。
使用持久检出目录准备环境，已登记为本地市场的目录不能当测试临时目录删除。

## 准备独立运行环境

在仓库根目录，Windows 运行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File runtime/setup.ps1
```

macOS、使用 glibc 的 Linux 或 WSL 运行：

```bash
sh runtime/setup.sh
```

脚本从 uv 官方 GitHub 发布下载固定的 0.13.6 版本，执行前核对已登记 SHA256 和大小。
优先复用 Python 3.11–3.14；缺少时准备私有 Python 3.12。
`runtime/requirements.txt` 固定依赖，通过 wheel 安装到独立环境，再验证本插件 CLI。
无需管理员权限，不修改系统 Python、Shell 配置或 PATH。

默认位置：Windows 为 `%LOCALAPPDATA%/PaperAlchemist/runtime`，macOS/Linux 为
`${XDG_CACHE_HOME:-~/.cache}/paper-alchemist/runtime`。可选变量
`PAPER_ALCHEMIST_RUNTIME` 用绝对目录覆盖默认位置；在用户执行环境中保留其选择。
Windows 与 WSL 使用各自环境。准备后将解释器位置写入 `runtime.json`，入口按依赖文件
哈希选择环境，可重复运行。安装中断后若留下锁或不完整环境，先检查精确路径与运行进程，
再修复。

本版仅有 Windows x86-64 和 Linux x86-64 的本地验证。下载清单还覆盖 Windows ARM64、
macOS/Linux ARM64 和 macOS x86-64；这些组合仍需对应平台验证。缺少 wheel 或系统不受支持
属于安装失败，不代表可以静默编译或安装系统包。PDF/OCR 和 LaTeX 属于可选的独立任务。
首次下载需要联网；这不是完整离线环境包。普通写作命令不下载运行环境。

## 安装原生插件

私人版：

```bash
codex plugin marketplace add git@github.com:Wang-Ruibin/paper-alchemist-private.git
codex plugin add paper-alchemist@paper-alchemist-private
```

公开空白版：

```bash
codex plugin marketplace add https://github.com/Wang-Ruibin/paper-alchemist.git
codex plugin add paper-alchemist@paper-alchemist
```

仅安装用户选择的版本，不同时启用两个版本竞争同名技能。从 Codex 读取实际安装路径，
不猜缓存目录。桌面端若还需通过插件浏览器操作，引导用户完成，并区分仍待操作与 CLI
已经完成安装。

## 验证实际安装副本

检查 Codex 插件清单，再调用实际安装副本。Windows：

```powershell
& <installed-plugin-root>/runtime/run.ps1 --version
& <installed-plugin-root>/runtime/run.ps1 validate-plugin <installed-plugin-root>
```

macOS/Linux：

```bash
sh <installed-plugin-root>/runtime/run.sh --version
sh <installed-plugin-root>/runtime/run.sh validate-plugin <installed-plugin-root>
```

私人版还需通过该入口执行 `validate-profile --workspace <temporary-folder>`，核对就绪状态
及清单来源数，不需要原始 PDF。公开版确认不存在 `skills/paper-alchemist/assets/corpus/`，
说明写作前需要蒸馏或导入指导，不创建虚假的已完成画像。检查状态保存在研究与插件状态
目录之外，完成后删除精确临时目录。

用日常语言说明版本、环境是否可用、还缺什么。新建对话发现 `$paper-alchemist`；未经核实，
不宣称当前会话已刷新。升级时刷新选定市场，通过受支持命令仅替换该插件，保留用户画像与指导。

来源：[OpenAI 插件打包](https://developers.openai.com/plugins/build/plugins)、
[uv 安装](https://docs.astral.sh/uv/getting-started/installation/)、
[Python 环境可移植性](https://docs.python.org/3/library/venv.html)。
