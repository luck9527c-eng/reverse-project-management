# 项目验收、关联审计与证据争议

项目级记录集中在 `re/project.json`，由 [project.json](../assets/project.json) 初始化。这里存验收、阶段审计和争议，实验事实仍留在 run.json，路线状态仍留在路线文件；INDEX 自动汇总未闭合事项。

## 项目验收

开工时把用户目标写成 goal、scope 和可核验的 acceptance 条目，明确目标版本/配置、交付文件、成功证据及允许保留的局限。初始 status 为 active；项目完成与某条路线 validated 分别判断。需求变化时保留变更原因和原范围，避免事后降低判据迎合现有结果。

验收条目的可执行形状：

```json
{
  "id": "A-001",
  "requirement": "在 T-001 的指定配置下复现交付文档描述的行为",
  "target_ids": ["T-001"],
  "status": "pending",
  "evidence": [],
  "deliverables": [],
  "reason": "",
  "min_independent_sources": 1
}
```

证据取得后填入已完成且封存的 RUN ID，交付物用 `{"path":"re/docs/result.md","sha256":"实际64位小写哈希"}` 引用，reason 解释证据怎样满足判据，再标 met。`target_ids` 表示全部目标都要覆盖：每个目标均须有匹配证据，并分别满足 min_independent_sources，不能用 A 目标的额外来源填补 B 的缺口。来源数量不能替代覆盖率或证据质量判断。纯文档交付也应有真实来源/复现运行；不能为满足字段编造实验。

完成前：

1. 每条验收标准都有匹配目标范围的证据，交付物可取回，命令与依赖足以让接手者复现。
2. 阶段审计覆盖当前记录，关联条件的复查/重验没有待办。影响验收的争议已解决；critical 只补充标识项目级阻塞，改成 false 不能放行受影响的验收。
3. 活动实验已结束，活动路线已闭合或明确暂停并记录处置，副作用已核查并恢复，或有核实后确实无须恢复的说明。剩余计划路线、非关键争议、未知和范围外工作在 completion.limitations / completion.handoff 披露，写清原因及下一步。
4. 刷新 INDEX，执行 `check <root> --hashes --complete`，人工核对判据与原始证据。检查通过后才可声明完成；设置 status 为 completed 后，普通 check 也会执行完成门槛。

预算耗尽可交接未完成项目，保留 active 与未满足标准，并写明停止原因。没有验收条目的新项目可以通过结构检查，不能通过完成检查。新证据使验收失效时把项目恢复为 active，保留原验收判断及更正原因，重新处理待办。

## 阶段关联审计

`impact` 只能遍历已登记的关系。首次接管、阶段结束、交接、准备完成时，对照**所有历史路线**与本阶段的新发现、工具能力变化、旧对照失效情况，检查漏掉的前提/阻塞关联；包括 falsified、validated、paused、blocked、superseded。不能只看当前活动路线或 impact 的输出。

1. 运行 `audit-scope <root>` 取得当前 snapshot；逐条读路线的问题、阻塞、closure 和重开条件，与新证据和共享条件比较。
2. 发现遗漏时补建 C 或 condition_ids，重新运行 impact，记录适用范围判断/重验计划。没有关联也记录 no_change 及具体理由。尚未读完或无法判断记 follow_up、next_step、stop_when，留在待办。
3. 完成必要修改后再次获取 snapshot，在 project.json.audits **追加**如下记录。每条路线只有一个审计项；linked 项必须列明已实际补入的 condition_ids。未解决的复查不能靠写 linked 消除。

```json
{
  "at": "2026-10-21T10:00:00Z",
  "trigger": "阶段交接",
  "snapshot": {},
  "route_reviews": [
    {
      "route_id": "R-001",
      "outcome": "no_change",
      "reason": "对照本阶段发现与旧证死范围，观测限制与此次新能力无关；记录实际比较依据"
    }
  ]
}
```

把 audit-scope 输出对象中 `snapshot` 字段的值赋给审计记录的 `snapshot`，不复制外层包装；空对象只是形状说明。脚本输出不会代做语义审计；不要生成一批未实际阅读的 no_change。审计结果没有新变化时可复用仍覆盖当前范围的最后一次审计，不重复造记录。

snapshot 覆盖目标清单、全部路线/条件/运行记录、环境、封存基线、专题文档、复用脚本、仓库配置，以及项目目标/验收/争议。新增或修改这些材料会让 INDEX 提示重新审计；可基于差异增量检查，但最后一份审计仍列出所有路线。审计记录自身不参与指纹，避免写入即过期；INDEX 的手写摘要与技能实现也不参与，相关实质发现必须落入权威记录。raw 字节完整性另用 --hashes 检查。

## 矛盾证据与有争议结论

同一主张在可比范围内出现相反证据时，在 disputes 追加 D-*：claim、scope、route_ids、supporting 与 contradicting（均为运行 ID）、critical、status（open/resolved）和 resolution；可用 acceptance_ids 显式关联验收项。原始证据、旧 closure 和路线 history 全部保留。

- 未解释冲突时用 open，执行 impact 检查 dispute_impacts：显式关联路线、消费争议证据及其派生来源的路线、相关共享条件的消费者以及硬依赖下游均受影响。原 status 仍表达历史判定；当前受影响的 active 路线须阻塞或暂停，不能继续借用历史 validated 作为有效前提。
- 无论 critical 为何值，引用争议证据/同源派生证据、受影响路线或显式 acceptance_ids 的验收项均不能保持 met，先恢复 pending 并记录原因。条件判断不确定时更新 C 的 revision，state 可退回 unknown，并触发下游复查。
- 先比较目标哈希、参数、环境、触发、窗口、覆盖和观测链，再设计能区分解释的最小对照。无法比较的证据先明确范围差异，不强行投票。
- 解决后填写 resolution：at、reason、outcome、evidence；说明是哪个观测/解释被更正，还是双方仅在不同范围成立。关联路线、条件版本、history 与摘要同步更正，旧依据保留。关键争议不能通过改名“非关键”或删除反证完成验收。
- 一份抓包、转储或同次运行的日志、截图、反编译结果与摘要可能互相解释，但不能据此称为多份独立验证。

## 证据来源链

独立采集运行的 provenance 形状：

```json
{
  "kind": "acquisition",
  "capture_id": "CAP-20261021T100000Z-01",
  "captured_at": "2026-10-21T10:00:00Z",
  "raw_artifacts": ["re/runs/RUN-observe/raw/events.log"],
  "source_runs": [],
  "note": "实际采集动作、原始来源及独立性理由"
}
```

capture_id 标识真实采集事件，captured_at 必须位于本次运行起止之间，raw_artifacts 非空且全部登记在 run.artifacts 中。同次采集的多次导出共用采集身份；新建 RUN ID、换工具读取或重复导入旧文件都不产生独立采集。复制旧文件仍须保留原来源并作为 derived 追溯。

处理已有证据的导出/转换运行使用 derived，source_runs 引用直接来源的已完成运行，note 写实际步骤；脚本递归追溯到 acquisition 并检测循环。相同 capture_id、相同规范化原始路径或同一文件的硬链接合并计数；不同真实采集恰好输出相同字节不自动合并。run.artifacts 中的 derived 文件仍填写 parents 和 generated_by，使文件级的生成链可追溯。若同时生成摘要和采集新证据，拆开来源边界，避免给摘要冒领新来源身份。

两个独立采集事件也可能共用同一个失效工具或同一错误前提；人工审计须判断独立性及共同误差，不能只看脚本计算的数量。脚本无法仅凭不同路径判断文件是否复制而来。旧记录缺采集字段不计独立来源；只在核实后、封存前补录，无法确认就保留缺口。执行封存规则对旧终态运行同样适用。

## 兼容旧项目

保留现有目录和配置，比较项目副本差异，补入 governance.py、integrity.py 及相关辅助脚本/模板和规则指针，并从种子创建 re/project.json。旧项目没有项目记录时 INDEX 显示待补齐；现有终态运行仍须核实身份、环境哈希和执行事实后封存。无法核实的历史材料按布局规则保留为遗留材料，不挪用新采集补全旧事实。完成检查要求补齐验收、审计和已启动实验的状态评估。
