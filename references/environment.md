# 本机环境与工具补齐

## 四层就绪状态

每个项目按当前路线需要选择工具，分别记录：

| 层级 | 证据 |
|---|---|
| discovered | 可定位的可执行文件、包或配置路径；记录发现方式 |
| executable | 实际版本/帮助或无害冒烟命令成功，记录命令、版本和输出 |
| session_ready | 当前 agent 可调用相应 MCP 或执行环境；记录实际调用或工具清单来源 |
| target_ready | 当前目标的平台、位数、权限、版本和所需 provider 匹配；记录最小无害验证 |

每层用 unknown / pass / fail / not_applicable 表示。失败保留原因和解除条件。PATH 找不到只表示 PATH 未发现，继续检查既有安装目录、包管理器和 MCP launcher，再决定安装。

环境快照存 `re/env/ENV-<unique>.json`，INDEX 手写区链接当前快照。至少包含时间、主机/系统版本、宿主架构、shell、目标需求、工具路径/版本、四层状态、安装变更和阻塞。

`project.py probe` 是跨平台的轻量发现器：只读取系统信息、PATH 和常见客户端配置文件是否存在。它不会启动候选工具、读取配置内容或判断实际 MCP 连接，GUI/便携安装也可能不在结果中。人工补充的检查结果和实际输出归入新快照或对应运行记录。

Windows 内核路线另外核实：系统构建、CPU 虚拟化能力、当前 hypervisor/VBS/Hyper-V 状态、管理员权限、驱动和符号配置、重启需求；以当前工具官方兼容矩阵为准。用户名或管理员账号名称不能证明当前 token 已提升。

## 自动补齐策略

选型顺序：当前会话的成熟工具能力 → 已安装工具的 CLI/导出能力 → 补齐所需官方工具或 provider → 经证实的能力缺口所需的最小自定义补充。优先取得工具的结构化结果和原始导出，再做轻量整理；不为读取已支持的二进制、包、协议或转储格式重造解析器。路线记录保留选型依据与工具来源，便于后续 agent 复用。

用户授权“缺少工具自行安装”时，以下步骤在该授权范围内直接推进，不重复索取笼统确认：

1. 确认下一条路线需要的能力、现有工具能否满足，查安装包/工具当前官方文档和兼容版本。记录来源 URL 和查阅时间；不要从 skill 中猜包名、开关或固定一个“永远最新”的版本。
2. 选择隔离度合适的安装方式：Python 虚拟环境、项目私有 npm prefix、便携目录或已有包管理器。使用明确版本，保存安装器哈希、签名或可信包源记录。
3. 记录安装前后版本、安装位置、命令、退出码、依赖和配置差异。修改配置前备份并局部合并，保留其他 MCP、PATH 和客户端设置。REA setup 若可能替换已有 skill，先检查实际计划，避免丢失自定义内容。
4. 安装后验证 executable，再验证 session_ready 和 target_ready。失败时修复实际失败层；本轮连续两次无新信息的修复失败后标记 blocked，保存诊断并继续其他可推进路线。
5. 清楚记录撤销方式、临时端口/进程/驱动、是否需重连或重启。当前会话不能刷新工具目录时如实交接，CLI 可用性单独记录。

安装授权按实际范围解释。需要整机重启、改变引导/驱动签名或安全配置、侵入现有 hypervisor、付费许可证、账号登录等额外影响时，先核实是否已授权；没有覆盖才为具体变更说明影响并请求必要操作。避免把这些变化绑定为所有项目的启动前置条件。

只配置当前项目实际需要的工具。不为了“齐全”批量安装全套工具，也不为恢复 MCP 顺手升级整个系统。已经适配的环境在新会话做廉价复验，版本、目标或故障发生变化时才扩大检查。

## 能力矩阵

下表是候选能力，按目标选择，已有等效工具可复用。

| 能力/目标 | 候选工具 | 需要确认的配置 |
|---|---|---|
| 通用可复现环境 | Git、Python、Node/npm、rg、7-Zip、SHA256 工具 | 版本、PATH、venv/prefix；Node 按 REA 实际运行要求 |
| REA MCP 编排 | REA 官方包与客户端 MCP 配置 | 客户端 ID、启动命令、版本、实际工具暴露、provider 可用性 |
| 原生静态工具 | Ghidra + 对应 JDK、IDA（已有许可证）、LLVM/binutils、Detect It Easy | 版本和架构；引擎存在与 MCP provider 可调用分开验证 |
| Windows 用户态 | WinDbg、x64dbg、Sysinternals Process Monitor / Process Explorer | 符号缓存/服务器、位数、权限、日志输出位置 |
| 动态插桩 | Frida CLI/Python、对应 server/gadget（需要时） | host/server/gadget 兼容版本、目标位数、传输与附加能力 |
| Windows 内核/虚拟化 | HyperDBG、WinDbg 内核调试 | CPU/OS 支持、hypervisor/VBS、驱动、权限、重启与隔离环境 |
| Linux/macOS 原生调试 | GDB/LLDB、strace/ltrace（适用平台） | ptrace/签名/权限限制、架构和系统版本 |
| .NET / JVM / Android | ILSpy、dnSpyEx、JDK、JADX、apktool、Android platform-tools | 运行时、字节码版本、设备/模拟器；按目标择取 |
| 网络与 IPC 记录 | Wireshark/TShark、适用的抓包驱动、mitmproxy；现有 Fiddler 可复用 | 捕获接口与权限、代理范围、证书变更与撤销、保存格式 |
| 固件/文件系统 | Binwalk/Unblob、所需解包器；必要时 WSL/容器 | host/provider 平台支持、依赖、挂载和可复现镜像版本 |
| 转储与内存记录 | ProcDump、Volatility 3（按需求） | 采集条件、符号、转储格式与保存大小 |

官方入口：

- REA：https://github.com/morluto/rea
- HyperDBG：https://docs.hyperdbg.org/
- Frida：https://frida.re/docs/installation/
- Ghidra：https://github.com/NationalSecurityAgency/ghidra
- WinDbg：https://learn.microsoft.com/windows-hardware/drivers/debugger/
- Sysinternals：https://learn.microsoft.com/sysinternals/
- x64dbg：https://x64dbg.com/
- Wireshark：https://www.wireshark.org/docs/

这些是查阅入口，不是已核验的安装配方；安装时依据所选版本的官方发布说明和实际 CLI help。

## REA 的特殊检查

区分四件事：skill 已存在、MCP 注册已写入、当前会话已连接、所需分析引擎可用。一个成功的 doctor 不能替代其他三件事。

1. 从当前会话真实工具清单检查 REA；存在可用工具且无故障时直接复用。
2. 缺少工具时检查客户端 MCP 注册和启动日志，用已安装 CLI 的 help 确认 doctor/setup 参数。若需要下载包，先核实官方发布版本和 Node 要求，使用版本固定的调用。
3. 对注册修复先查看 dry-run（若该版本支持），备份并应用已授权的最小配置差异，保留其他 server 和自定义 skill。
4. 重连后验证实际工具出现在当前会话，再检查该路线需要的 provider。配置正确但本会话尚未重连时标为待重连，避免重复安装。
5. CLI 能运行而 MCP 不可调用时，两者分开记录。继续可用工作并交接会话恢复步骤。

## Frida 与 HyperDBG 的特殊检查

Frida 的版本命令成功只证明 CLI 可启动。还要检查 Python 环境、目标架构、host/server/gadget 版本关系、设备或本机连接、权限，以及在合适测试进程上的最小验证。不要通过安装 Frida 推断所有目标都可附加。

HyperDBG 不是每个项目的必选依赖。先确认是否有内核/虚拟化观测需求，再按当前官方支持条件核实硬件、系统、驱动与 hypervisor。下载工具与装载驱动分别记录；遇到必须改变整机配置才能验证时，保留诊断和解除条件，不把环境冲突当作目标路线证死。
