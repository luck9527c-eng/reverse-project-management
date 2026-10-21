# Reverse Project Management

面向逆向项目的工程管理 skill：用一份 `INDEX.md` 连接目标、环境、路线、证据、脚本和实验产物，让 agent 按证据推进并保留失败与重开条件。

## 能力

- 项目内初始化：生成仓库专属配置、管理目录和独立 skill 副本，沿用已有 agent 入口与目录约定。
- 证据驱动：绑定目标 SHA256，保留运行命令、工具版本、脚本快照、原始产物与来源链。
- 路线管理：区分阻塞、暂停、验证与证死；共享条件变化触发直接关联和下游路线复查，保留旧结论范围。
- 项目交接：检查历史路线的遗漏关联，维护验收、矛盾证据、同源去重和中断实验恢复待办。
- 工具优先：按路线需要检查并补齐 REA MCP、HyperDBG、Frida 等成熟工具，优先使用现有能力与导出。

完整工作流见 [SKILL.md](SKILL.md)；各项细则由其中的按需链接触达。

## 安装与使用

把本仓库克隆到 agent 使用的 skills 目录，例如：

```text
git clone https://github.com/luck9527c-eng/reverse-project-management.git ~/.agents/skills/reverse-project-management
```

在具体分析仓库中向 agent 发出请求：

```text
使用 $reverse-project-management 初始化当前仓库的工程管理。
先检查已有目录和 AGENTS.md/CLAUDE.md，沿用有效约定，建立 INDEX、项目配置和仓库内 skill 副本。
```

agent 会探索仓库并局部接入入口规则。辅助脚本的默认布局初始化可单独运行（Python 3.10+，仅标准库）：

```text
python <skill-dir>/scripts/project.py init <analysis-repository>
```

此命令生成根目录 `INDEX.md`、`docs/agents/reverse-project-management.md`、`.agents/skills/reverse-project-management/` 与 `re/` 记录目录。它拒绝覆盖已有管理目录；入口文件的合并由 agent 完成。已有项目按 [布局规则](references/layout.md) 适配。

初始化后，项目专属配置和状态在该分析仓库内维护，工具按实际路线需要安装与验证。共享模板的更新不会自动覆盖项目副本。

## 日常命令

在已初始化项目中使用仓库内副本：

```text
python .agents/skills/reverse-project-management/scripts/project.py seal . <RUN-id>
python .agents/skills/reverse-project-management/scripts/project.py impact .
python .agents/skills/reverse-project-management/scripts/project.py audit-scope .
python .agents/skills/reverse-project-management/scripts/project.py index .
python .agents/skills/reverse-project-management/scripts/project.py check . --hashes
```

声明项目完成前另加 `--complete`，并人工核对验收判据与证据。结构校验通过只说明记录满足检查条件。

每次运行事实补齐、原始来源核对后执行一次 seal，保存目标身份和执行摘要；将 re/seals 与记录一起提交 Git。后续 check 对照基线，--hashes 同时核验环境快照和产物字节。更正使用新记录，保留原封存；本地基线不证明首次记录真实。

验收逐目标检查采集来源，同一文件或其硬链接不能冒充多次独立采集。impact 同时列出条件复查和争议影响；受争议影响的活动路线与验收须先阻塞/暂停及恢复 pending，critical=false 不能绕过。

## 验证辅助脚本

在本仓库根目录运行：

```text
python -B scripts/test_project.py
```

测试使用临时项目，不启动分析目标或安装分析工具。
