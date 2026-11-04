# 工具发现、清单与刷新

发现本机工具、建立工具文档、切换会话或工具失效时读取。四层就绪和安装授权沿用 [环境管理](environment.md)，团队共享写入沿用 [团队协作](team-coordination.md)。

## 发现与验证

1. **确定来源。** 读取实际会话的工具清单/描述、PATH、已有工具记录、Windows 应用注册信息（适用时）和项目配置中的工具根目录。便携工具根由用户或已有配置提供；机器路径保存在分析项目配置，不写死到共享 skill。当前 agent 的 MCP 清单不能代替另一个宿主会话的清单。
2. **登记候选。** 对已指定根进行有限深度的文件元数据扫描，匹配已知入口及目录标记。默认深度 4、总访问条目 10000，可在项目配置调整；保存来源、覆盖范围、跳过项和扫描失败。安装包/缓存、文档和 SDK 示例不当成已安装入口。默认不沿 junction/symlink 扩大范围。只因扫描未命中就记 unknown，不推断整机没有工具。
3. **确认使用方式。** 区分原生 CLI、脚本/Python 接口、MCP 与 GUI；一个程序可以有多个入口。已有 MCP 优先复用；可通过 shell 使用的原生工具不必额外挂 MCP。先查实际说明和已有配置，再为当前路线执行最小无害验证，保留真实输出。仅找到桥接 exe 不能证明 MCP 已挂载；只读发现不启动工具、安装插件、附加目标或开始采集。
4. **保存清单。** Lead 按下节结构发布 JSON，派生 Markdown，更新 INDEX 指针。工兵只交回发现/验证材料，由 Lead 合并。单人工作时 agent 直接按同一结构维护，不必启用团队。

需要机器可读的扫描配置时，在分析项目保存 `docs/agents/tool-discovery.json`，从项目“工具环境”章节链接；不放进要求环境快照结构的 re/env。字段为 schema_version=1、host.id、roots、known_entrypoints、exclusions、max_depth、max_entries。路径数组使用显式绝对路径；排除项按路径边界匹配，根深度为 0，总条目上限包括目录。无配置就不猜便携根。共享 skill 不预填某台机器的实际路径。

现有 `project.py probe` 只做 PATH 和配置路径发现，没有实现指定目录扫描、工具清单合并或 Markdown 生成。不要把以下工作流描述成该命令已具备的能力；agent 可用已有文件/系统工具调查，若需稳定重复执行的扫描/渲染逻辑，将辅助脚本放在本 skill 的 scripts 内。dsh-redteam-plugin 不消费工具清单，也不做能力匹配或派发前检查；清单只服务 agent 自己的判断与 Lead 的派发决定，单人项目同样可维护。

## 单一数据源与历史快照

- `re/env/tools.json`：当前结构化工具清单，是 Markdown 的唯一数据源。
- `re/env/tools.md`：生成的可读文档；用户备注保存在 JSON 的 notes/limitations，不单独维护第二份工具状态。
- `re/env/ENV-tools-<unique>.json`：发布时保存的不可变快照。RUN 的 environment.snapshot/snapshot_sha256 指向此快照，不能指向会刷新覆盖的 tools.json。

JSON 顶层保留现有环境快照兼容字段 `schema_version: 1`、带时区的 collected_at、host 对象与 tools 数组。另含 inventory_revision、snapshot_ref、discovery_scope、registry_ref。host.id 表示所属机器/环境，不能把另一机器的路径当成本机可用。discovery_scope 保存根目录、深度、来源、覆盖/跳过/失败信息；registry_ref 是实际宿主/会话工具清单的保存引用，未读取时为 null。

每个 tools 项含 id、name、version（未知为 null）、version_source、capability_candidates、entrypoints、notes、limitations、next_step。工具 ID 稳定，多个版本/安装实例以不同实例 ID 区分；目录名推测的版本明确标记 inferred，不冒充命令验证。

每个 entrypoint 含 id、kind（cli/python/mcp/gui）、path 或 MCP server/tool_names、transport_tools、invocation（未验证为 null）、discovery、states、checks。states 包含 discovered/executable/session_ready/target_ready，每项取 unknown/pass/fail/not_applicable。checks 记录层级、时间、结果、宿主/session、目标范围、原因与证据引用。不同入口/会话/目标的成功不相互代填。

invocation 保存已核实的 program、参数模板、cwd 规则、输出约定、来源/验证引用和资源要求；只登记事实，不因为写进清单就自动执行。GUI 入口找到了也可能没有 agent 可用的控制通道，须明确限制。capability_candidates 是候选标签，不能直接作为已满足的能力判据。

Markdown 开头标明由 tools.json 生成、inventory_revision、collected_at、host.id、源 JSON 的 SHA256 与快照链接；正文给出发现范围、工具总览、各入口的路径/版本/能力/调用方式/四层状态/验证时间/证据，以及缺口和下一步。未验证的调用示例留空或写未验证，不猜参数。目录超深、读取失败和过期状态必须可见。

发布顺序是保存不可变快照，再原子替换 tools.json，最后生成并原子替换 tools.md。JSON 是快照字节的当前副本，不独立修改两个版本；无实质变化可复用原 revision。JSON/MD 跨文件写入不是原子事务，文档的源哈希不匹配时重新生成，不能让旧 Markdown 影响能力判定。现有 check 只做环境记录基本结构检查，不验证清单的语义或生成一致性。

## 刷新、提醒与接手

启动时先读已有清单；第一次使用相关工具前检查路径/版本/入口与当前 session。配置的根目录、MCP 工具集合、程序版本、连接或目标变化时，增量刷新相关记录并重新验证必要层级；不每次派发都递归扫整盘。探测失败保留历史和当前缺口，不删除旧验证证据。

出现影响当前任务的未知/失败，主动说明：已找到什么、具体不可用的层级、影响哪些路线、最小下一步以及其他可继续的路线。相同缺口未变化时不在每轮重复提醒；缺口首次出现、发生变化、恢复或需要用户动作时再报告。未找到可用方式时交回具体阻塞，不擅自安装、不把诊断失败当证死，也不创建后台监控。

INDEX 手写区链接 tools.md 和最新快照；正式运行各自保留所用旧快照。现有 index 自动导航会列环境 JSON，tools.md 指针由 Lead 维护；共享模板更新不自动覆盖已有项目副本。
