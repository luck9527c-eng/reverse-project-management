---
name: reverse-project-management
description: 适用于建立或接管逆向项目的工程管理、维护 INDEX 总入口、组织脚本与实验产物、管理证据和路线证死、跨路线发现触发复查，以及检查和补齐本机工具环境时。
---

# 逆向项目工程管理

让新会话仅凭 `INDEX.md` 找到当前目标、可信结论、验证路线、环境缺口和下一步，再沿链接回到原始证据。**每个结论有适用范围，每次实验可追溯，每条路线有退出条件。**

## 模板与项目实例

共享 skill 是初始化模板。确定具体分析仓库后，生成仓库专属的 `docs/agents/reverse-project-management.md` 配置、根目录 `INDEX.md` 和 `re/` 管理目录，并在已有 agent 入口中接入读取规则。默认同时在 `.agents/skills/reverse-project-management/` 保存项目副本，使仓库可独立交接。

项目特有目录、工具策略和 consumer rules 以仓库配置文档为权威来源，后续直接修改它；路线、证据与环境变化写入项目记录。共享模板保持不变。项目副本只在需要调整项目工作流实现时修改；升级先比较差异，保留项目约定。

如果当前目录是共享 skills 目录或 skill 自身，先取得用户指定的分析仓库路径；不能把这里当作分析项目初始化。已有项目副本时从它接手，初始化不是每轮的重置操作。

## 首次配置仓库

这是按仓库探索并落盘配置的流程，脚本只辅助建立默认目录与校验记录。

1. **探索已有约定。** 读取根目录 `AGENTS.md`、`CLAUDE.md`、INDEX、`docs/agents/`、现有脚本/产物目录及仓库内 skill；检查是否已经配置。列出可复用内容、缺口和路径冲突。
2. **确定本仓库配置。** 简述拟采用的目录映射、agent 入口、工具补齐策略及已有文件的合并方式。已有约定或本会话已确认的选择直接复用；只询问影响落盘结果且无法推断的分歧，不把每个默认值变成确认题。
3. **写入项目配置。** 新项目可运行 `init`，再把生成的 [配置种子](assets/project-management.md) 调整为本仓库的真实选择。已有项目按种子局部合并，复用其 INDEX 和材料，避免重置。
4. **接入 agent 入口。** 优先编辑已有 `CLAUDE.md`，否则编辑已有 `AGENTS.md`。两者均存在时保留双方原内容，避免建立互相冲突的规则；两者均无时按已知运行环境选入口（Codex 默认 AGENTS.md），已有用户偏好优先。更新 `## Agent skills` 下的 `### Reverse project management` 子节，只维护该子节，不重复追加或替换整个文件：

   ```markdown
   ### Reverse project management

   开始逆向项目工作先读 INDEX.md。目录、证据、路线和工具约定见
   docs/agents/reverse-project-management.md；按当前任务读取其中链接的规则。
   产出证据或改变路线后同步记录和 INDEX，交接前执行项目校验。
   ```

5. **验证与交接。** 在 `re/project.json` 登记目标、范围与可核验的项目验收标准，按 [验收与审计](references/acceptance-audits.md) 记录阶段审计。从入口检查配置、INDEX、规则和证据的导航链；刷新索引并校验。报告选择的路径及实际环境状态。后续直接维护仓库配置与记录。

脚本 `init` 不机械修改 AGENTS.md/CLAUDE.md；第 4 步由 agent 在读取现有内容后完成。目录创建成功本身不代表仓库配置已经接入。

## 接手顺序

1. 确认项目根目录，先读现有 agent 入口、`INDEX.md` 和 `docs/agents/reverse-project-management.md`。按仓库配置接手；尚未配置时先走首次配置流程。保留已有有效布局，避免为了统一目录搬动样本、覆盖文档或打断脚本路径。
2. 固定目标身份：路径、SHA256、版本、平台、架构、来源。哈希变化即新目标记录，旧证据保留原绑定。尚未取得的信息写 `unknown`，明确下一步如何确认。
3. 新项目用下列 `init` 建立入口；已有项目先盘点，再选择迁移或适配。INDEX 是唯一总入口，详细材料沿链接按需读取。
4. 阅读 [环境管理](references/environment.md)，检查当前主机与当前 agent 会话的能力。按下一条路线所需补齐工具；有现成工具时先验证。记录安装、配置、重连、目标兼容性各自的结果。
5. 阅读 [证据与路线](references/evidence-routes.md)，检查历史结论是否有原始来源、运行上下文及适用目标；先核查遗留 running/interrupted 实验和副作用，再恢复工作。缺失部分作为证据缺口保留。选择依赖已满足、信息收益高且成本可控的路线。

接手完成的条件：INDEX 指向目标清单、当前环境快照、路线记录和已有证据；下一步可直接执行，阻塞项有明确解除条件。

## 每轮工作

1. **先定义判定。** 建立或更新 `R-xxx`：问题、假设、目标、依赖、最小实验、预期观察、反证条件、预算。关键前提、阻塞点和解除条件用共享 `C-xxx` 记录并关联路线。检查相同目标与前提下的既有失败，写清本次有什么变化。
2. **再建立运行目录。** 使用唯一 `RUN-...` ID；运行前保存计划、命令、初始状态、预期副作用与恢复方案，结束后补齐执行事实、采集事件、来源链、原始输出与环境快照哈希，核对原始来源后执行 `seal` 封存，再用于结论或验收。失败、超时、空结果和中断同样保留；具体字段见 [运行记录](references/evidence-routes.md#每次运行的记录)。
3. **依证据更新并复查影响。** 区分观察事实、推断、假设和未知；引用 `run.json` 及文件内定位。关键新证据或工具/前提变化时，按 [跨路线复查](references/cross-route-review.md) 更新条件版本，自动检查直接关联路线及下游依赖，记录范围判断或最小重验计划。只在 [状态门槛](references/evidence-routes.md#路线状态) 满足时变更路线，保留历史与相反证据。
4. **同步入口并交接。** 更新 INDEX 的已知事实摘要、当前路线、阻塞和下一步。阶段结束或交接时按 [验收与审计](references/acceptance-audits.md) 检查全部历史路线的遗漏关联；矛盾证据登记争议，同源产物不算独立验证。用 `index` 和 `check` 检查导航与待办。声明项目完成前另执行 `check --hashes --complete` 并人工核对验收证据；未闭合项如实交接。

预算耗尽、工具失效、抓取失败归入暂停或阻塞；**证死需要有效反证和覆盖范围**。新版本、新前提或新证据可以重开，必须说明重开原因。

## 工具优先

建立实验前先查当前会话的工具清单、已安装工具及官方能力。REA MCP、HyperDBG、Frida 等成熟工具能完成的工作，优先使用其现有命令、provider 和导出结果；缺配置或依赖时先修复实际缺口。工具能分页、筛选或导出时，使用这些能力取得原始证据。

**已有工具覆盖的格式和能力，不另写解析器替代。** 工具输出的筛选、归档、格式转换可以用轻量脚本；只有核实成熟工具确实不覆盖需求，才建立最小自定义补充，并在路线中写明已查工具、能力缺口、自定义范围和交叉校验方法。工具调用失败属于环境诊断，不能直接成为重写解析器的理由。

## 可执行辅助

`<skill-dir>` 指本 SKILL.md 所在目录，`<project-root>` 指待管理项目；路径含空格时加引号。Python 3.10+，仅使用标准库。

```text
python <skill-dir>/scripts/project.py init <project-root>
python <skill-dir>/scripts/project.py probe --output <project-root>/re/env/ENV-unique.json
python <skill-dir>/scripts/project.py seal <project-root> <RUN-id>
python <skill-dir>/scripts/project.py impact <project-root>
python <skill-dir>/scripts/project.py audit-scope <project-root>
python <skill-dir>/scripts/project.py index <project-root>
python <skill-dir>/scripts/project.py check <project-root>
python <skill-dir>/scripts/project.py check <project-root> --hashes
python <skill-dir>/scripts/project.py check <project-root> --hashes --complete
```

- `init` 建立项目配置、管理目录和仓库内 skill 副本，遇到已有配置、INDEX、`re/` 或同名项目 skill 时拒绝写入。已有项目先盘点，再手动按模板适配；复用已存在的配置与项目副本。
- `probe` 只发现主机、PATH 和常见 MCP 配置文件的位置，不安装、不执行发现的工具、不证明可用性；输出文件必须是新文件。
- `seal` 对已结束运行执行哈希与记录预检，保存目标身份和执行记录的独立基线；拒绝覆盖已有封存。基线随项目进入经审阅的 Git，更正使用新记录，详见 [保全规则](references/evidence-routes.md#执行封存与更正)。
- `impact` 输出条件复查与未解决争议的影响队列，沿证据来源、共享条件和路线依赖传播；受争议影响的活动路线先阻塞或暂停，保留历史结论。
- `audit-scope` 只读输出阶段审计范围指纹；agent 实际检查所有历史路线后，将指纹与逐路线判断追加到项目记录。
- `index` 只替换 INDEX 中的导航标记区，更新材料导航和待复查队列，保留手写目标、决策和交接。
- `check` 检查引用、封存、复查、依赖、证死、逐目标验收、采集去重和恢复记录，并返回未闭合项数量；`--hashes` 核验目标、环境快照、脚本、产物和交付物；`--complete` 要求验收及完成门槛闭合。检查不能替代对实验有效性、证据独立性和结论逻辑的判断。

## 按需材料

| 当前工作 | 读取或复制 |
|---|---|
| 初始化、接管、整理文档与产物 | [项目布局](references/layout.md)、[配置种子](assets/project-management.md)、[INDEX 模板](assets/INDEX.md) |
| 立路线、记录实验、证死、重开、处理冲突 | [证据与路线](references/evidence-routes.md)、[路线模板](assets/route.json)、[运行模板](assets/run.json) |
| 关键新发现、共享阻塞解除、旧前提变化、跨路线重验 | [跨路线复查](references/cross-route-review.md)、[条件模板](assets/condition.json) |
| 项目验收、阶段交接、遗漏关联审计、证据争议与来源独立性 | [验收与审计](references/acceptance-audits.md)、[项目记录模板](assets/project.json) |
| 检查本机配置、装工具、接 MCP、处理环境阻塞 | [环境管理](references/environment.md) |

交付时报告实际落盘位置、已验证事项和仍缺证据的事项。记录仍缺关键字段时交付真实的未完成状态。
