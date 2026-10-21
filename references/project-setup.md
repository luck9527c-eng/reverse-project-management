# 首次配置分析仓库

这是按仓库探索并落盘配置的流程，脚本只辅助建立默认目录与校验记录。

1. **探索已有约定。** 读取根目录 `AGENTS.md`、`CLAUDE.md`、INDEX、`docs/agents/`、现有脚本/产物目录及仓库内 skill；检查是否已经配置。列出可复用内容、缺口和路径冲突。
2. **确定本仓库配置。** 简述拟采用的目录映射、agent 入口、工具补齐策略及已有文件的合并方式。已有约定或本会话已确认的选择直接复用；只询问影响落盘结果且无法推断的分歧，不把每个默认值变成确认题。
3. **写入项目配置。** 新项目可运行 `init`，再把生成的 [配置种子](../assets/project-management.md) 调整为本仓库的真实选择。已有项目按种子局部合并，复用其 INDEX 和材料，避免重置。
4. **接入 agent 入口。** 优先编辑已有 `CLAUDE.md`，否则编辑已有 `AGENTS.md`。两者均存在时保留双方原内容，避免建立互相冲突的规则；两者均无时按已知运行环境选入口（Codex 默认 AGENTS.md），已有用户偏好优先。更新 `## Agent skills` 下的 `### Reverse project management` 子节，只维护该子节，不重复追加或替换整个文件：

   ```markdown
   ### Reverse project management

   开始逆向项目工作先读 INDEX.md。目录、证据、路线和工具约定见
   docs/agents/reverse-project-management.md；按当前任务读取其中链接的规则。
   产出证据或改变路线后同步记录和 INDEX，交接前执行项目校验。
   ```

5. **验证与交接。** 在 `re/project.json` 登记目标、范围与可核验的项目验收标准，按 [验收与审计](acceptance-audits.md) 记录阶段审计。从入口检查配置、INDEX、规则和证据的导航链；刷新索引并校验。报告选择的路径及实际环境状态。后续直接维护仓库配置与记录。

脚本 `init` 不机械修改 AGENTS.md/CLAUDE.md；第 4 步由 agent 在读取现有内容后完成。目录创建成功本身不代表仓库配置已经接入。


## 默认布局初始化

`<skill-dir>` 是当前模板目录，`<project-root>` 是具体分析仓库。Python 3.10+，仅标准库；路径含空格时加引号。

```text
python <skill-dir>/scripts/project.py init <project-root>
python <skill-dir>/scripts/project.py probe --output <project-root>/re/env/ENV-unique.json
```

init 拒绝已有 INDEX、re/、项目配置和同名项目 skill，也拒绝异常链接路径。已有项目沿用配置与副本，按 [布局规则](layout.md) 手动适配；首次配置不是重置操作。probe 只发现环境，不安装工具或证明其可用；就绪验证按 [环境规则](environment.md) 进行。

## 配置完成的判据

从实际 agent 入口可读到项目配置和 INDEX，再从 INDEX 找到目标、验收、当前环境、路线与下一步。核验项目副本可独立运行 index 和 check；目标尚未取得时保留真实空清单和待办，不为通过验收填占位哈希。报告入口、配置及副本的实际路径、检查结果和缺口。

项目特有目录、术语和安装选择直接维护项目配置；已有术语表/决策记录按任务读取并沿用，只在出现歧义或需要解释长期取舍时补充。更换配置才重新走相关步骤，日常推进不重复询问已确定选择。
