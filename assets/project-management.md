# 本仓库的逆向项目管理配置

本文件保存仓库专属选择。初始化时依据实际目录和已有规则调整；后续直接编辑本文件，并同步 INDEX 中的入口。共享 skill 不保存本项目状态。

## 路径映射

以下为默认值；已有目录有效时使用已有路径，并说明校验脚本所需适配。

| 用途 | 本仓库路径 |
|---|---|
| 唯一总入口 | `INDEX.md` |
| agent 读取入口 | 初始化时登记实际采用的 `AGENTS.md` 或 `CLAUDE.md` |
| 项目 skill 与辅助脚本 | `.agents/skills/reverse-project-management/` |
| 目标身份 | `re/targets.json` |
| 项目验收、阶段审计与证据争议 | `re/project.json` |
| 环境快照 | `re/env/` |
| 目标与执行封存基线 | `re/seals/targets/`、`re/seals/runs/` |
| 路线记录 | `re/routes/` |
| 共享前提与阻塞条件 | `re/conditions/` |
| 专题文档 | `re/docs/` |
| 复用脚本 | `re/scripts/` |
| 每次实验及原始/派生产物 | `re/runs/<RUN-id>/` |
| 样本、私有工具、缓存 | 按需使用 `re/samples/`、`re/tools/`、`re/tmp/` |

## Consumer rules

- 开始工作先读 INDEX 的当前工作集、目标身份、环境缺口与下一步，再沿链接读取相关路线和证据。首次接管额外阅读本配置和实际目录。
- 首次配置或改接入口时读 [仓库配置流程](../../.agents/skills/reverse-project-management/references/project-setup.md)。已有设置直接复用。
- 选路线、把宽泛目标拆成单轮问题、断点接手和交接时读 [工作会话规则](../../.agents/skills/reverse-project-management/references/work-sessions.md)。只领取当前前提可用且产出明确的工作；未细化问题留在 INDEX。
- 创建或整理材料时读 [目录与保全规则](../../.agents/skills/reverse-project-management/references/layout.md)。INDEX 管导航，详细事实保存在对应记录中。
- 建路线、处理负结果、证死或重开时读 [证据与路线规则](../../.agents/skills/reverse-project-management/references/evidence-routes.md)。结论绑定目标哈希；预算耗尽和观测失败分别记录为暂停或阻塞。
- 关键新发现或工具/前提变化时读 [跨路线复查规则](../../.agents/skills/reverse-project-management/references/cross-route-review.md)，更新共享条件版本，自动检查关联路线和下游依赖。旧结论保留范围，复查与重验按优先级和预算安排，并在 INDEX 保留待办。
- 定义验收、阶段结束、交接、声明完成或处理矛盾证据时读 [验收与审计规则](../../.agents/skills/reverse-project-management/references/acceptance-audits.md)。审计全部历史路线的遗漏关联，保留有争议结论和相反证据；同源导出不计作独立验证。
- 实验开始前登记初始状态、副作用与恢复方案；接手中断实验时先核查会话/目标实际状态，保存部分输出并评估恢复。操作见运行记录规则，不能直接重跑或冒记恢复完成。
- 运行结束后核对真实采集身份、环境快照哈希与产物，执行 seal，再引用为结论/验收依据；封存基线随项目进入经审阅的 Git。已封存执行事实使用新记录更正，恢复评估在 state 中追加。
- 验收覆盖 target_ids 中的每个目标并分别满足独立采集数量。open 争议影响沿来源、共享条件和路线依赖传播：活动路线先阻塞/暂停，受影响验收恢复 pending，critical=false 不能豁免。
- 检查或补齐工具时读 [环境规则](../../.agents/skills/reverse-project-management/references/environment.md)。区分发现、启动、会话可调用和目标适配。
- 成熟工具覆盖的工作优先使用 REA MCP、HyperDBG、Frida 等现有能力；缺连接先修环境，不以手写解析器代替已有能力。
- 产生证据或改变路线后更新对应记录和 INDEX。交接前刷新导航并校验，保留真实失败和未知项。

## 本仓库的工具与安装选择

- 工具按目标和下一条路线需要选取；当前选择及就绪状态记录在 INDEX 链接的环境快照中。
- 用户已授权自行补齐的工具在该范围内直接安装和验证，优先使用隔离环境或便携目录；需要额外授权的具体系统变更按实际影响处理。
- 安装命令、版本、来源、配置差异和撤销方式写入仓库记录，不回写共享 skill。

## 维护与校验

默认布局使用仓库内的辅助脚本：

```text
python .agents/skills/reverse-project-management/scripts/project.py seal . <RUN-id>
python .agents/skills/reverse-project-management/scripts/project.py index .
python .agents/skills/reverse-project-management/scripts/project.py impact .
python .agents/skills/reverse-project-management/scripts/project.py audit-scope .
python .agents/skills/reverse-project-management/scripts/project.py check . --hashes
```

项目完成前另加 `--complete`；普通结构校验通过不代表项目验收完成。项目记录维护本仓库的验收范围、证据与交付物，INDEX 汇总待办。

seal 在每次运行事实补齐后执行一次；index、impact 和 check 可重复执行。遇到已有封存不重写；更正工作按证据规则保留原运行与新运行的关联。

目录或工作流变化时，更新本配置、agent 入口和 INDEX；同时适配依赖这些路径的脚本。日常推进路线不需要重新初始化。
