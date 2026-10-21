---
name: reverse-project-management
description: 适用于建立或接管逆向项目的工程管理、维护 INDEX 总入口、组织脚本与实验产物、管理证据和路线证死、跨路线发现触发复查，以及检查和补齐本机工具环境时。
---

# 逆向项目工程管理

以 `INDEX.md` 为唯一总入口，让新会话找到目标、可信结论、路线、环境与下一步，再沿链接返回原始证据。**每个结论有适用范围，每次实验可追溯，每条路线有退出条件。**

## 先定位项目与当前任务

读取实际分析仓库的 agent 入口、INDEX 和 `docs/agents/reverse-project-management.md`。配置保存仓库约定，`.agents/skills/reverse-project-management/` 保存独立项目副本；后续项目状态与约定在仓库内维护。共享模板用于初始化，更新不会覆盖已有副本。

当前目录是共享 skills 目录或 skill 自身时，使用用户指定的分析仓库；未指定则取得路径。已有配置时直接接手，保留目录和历史记录。

| 当前任务 | 读取规则 |
|---|---|
| 尚未配置仓库、接入 agent 入口或适配已有配置 | [首次配置](references/project-setup.md)，使用 [配置种子](assets/project-management.md) |
| 整理路径、文档、脚本、样本与产物 | [项目布局与保全](references/layout.md) |
| 选择可领取路线、缩小单轮问题、断点接手或交接 | [工作会话](references/work-sessions.md) |
| 建路线、记录实验、证死或更正封存事实 | [证据与路线](references/evidence-routes.md)，使用 [路线](assets/route.json) / [运行](assets/run.json) 模板 |
| 新证据改变前提、解除旧阻塞、争议影响下游 | [跨路线复查](references/cross-route-review.md)，使用 [条件模板](assets/condition.json) |
| 定义验收、处理争议、阶段结束或声明完成 | [验收与审计](references/acceptance-audits.md)，使用 [项目模板](assets/project.json) |
| 当前路线缺工具、会话连接或目标适配 | [环境管理](references/environment.md) |

按触发场景读取规则。日常会话先看当前工作集，再读取所选路线的依赖、条件与证据；阶段交接/完成仍须按审计规则覆盖全部历史路线。

## 每轮闭环

1. **选择问题。** 按工作会话规则选出依赖可用、范围明确的路线；把本轮要减少的不确定性、目标、判据、预算及停止条件写入路线。宽泛目标先收敛，未细化事项留在 INDEX 并指向已有材料。
2. **记录并封存。** 使用唯一 RUN 目录，执行前保存计划、命令、初始状态与恢复方案；结束后补齐执行事实、采集事件、来源链、原始产物和环境快照哈希。核对原始来源后执行 seal，再用于结论/验收。失败、超时、空结果与中断同样保留。
3. **更新影响。** 区分观察、推断、假设与未知；引用运行和文件内定位。条件变化或争议出现时执行 impact，处理直接关联和下游影响，保留旧 closure 的范围及相反证据。证死须有通过验证且可定位的观测/对照链；预算耗尽、工具失效与抓取失败分别记暂停或阻塞。
4. **留下恢复点。** 同步权威记录和 INDEX 的下一步，刷新导航并 check --hashes；交接时完成关联审计并披露剩余待办。声明完成前另执行 check --hashes --complete，人工核对逐目标验收与实际证据。

## 工具优先

实验前检查当前会话工具、已有安装和官方能力。REA MCP、HyperDBG、Frida 等成熟工具覆盖的工作，使用现有命令、provider、分页/筛选和导出；只按下一条路线的实际缺口安装与验证。

**已有工具覆盖的格式和能力，不另写解析器替代。** 轻量脚本可筛选、归档或转换工具输出。自定义补充须先核实工具确实不覆盖，在路线记录已查工具、能力缺口、补充范围和交叉验证方式；调用失败先诊断环境。

## 辅助命令

在分析仓库使用项目副本；以下是一次已有运行结束后的维护顺序，RUN-id 换成实际 ID：

```text
python .agents/skills/reverse-project-management/scripts/project.py seal . <RUN-id>
python .agents/skills/reverse-project-management/scripts/project.py impact .
python .agents/skills/reverse-project-management/scripts/project.py index .
python .agents/skills/reverse-project-management/scripts/project.py check . --hashes
```

seal 只执行一次，拒绝覆盖已有基线；目标身份和执行封存随项目进入经审阅的 Git，更正使用新记录。审计时调用 audit-scope，将输出的 snapshot 字段值写入审计记录。参数以 project.py --help 和子命令 --help 为准；初始化命令见首次配置规则。

index 更新导航与待办，保留手写摘要；impact 输出条件复查和争议影响，均不代改路线结论。check 验证结构、封存、哈希和记录关系，不能证明实验有效、来源真实独立或结论逻辑正确；实际未完成事项如实交接。
