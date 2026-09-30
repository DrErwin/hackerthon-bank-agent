# Git 与提交约定

任何提交、分支、推送操作前读这份。分支策略、PR 门槛和 CODEOWNERS 规则在
[Review 与合并原则](../principles/03-review-and-merge.md)，本文件只管仓库当前状态与提交格式。

## 1. 仓库当前状态

**2026-09-27：私有远端已建立**：[DrErwin/hackerthon-bank-agent](https://github.com/DrErwin/hackerthon-bank-agent)，本地 `main` 跟踪 `origin/main`。

- GitHub Actions 已在 PR 和推送 `main` 时检查文档链接、改动文件空白错误和现有 Python 工具语法；首次远端运行通过。
- 仓库仅允许 squash merge，合并后自动删除远端功能分支。
- **`main` 尚未受 GitHub 强制保护**：当前个人账号方案下，私有仓库的分支保护和 Rulesets API 均返回需升级 GitHub Pro 或设为公开。团队现在须按约定使用 PR；平台暂不能拦住直推或未通过检查的合并。
- 团队 GitHub 账号暂未收集，CODEOWNERS 和强制负责人审批尚未启用。
- 团队分工按 `AGENTS.md` 的目录边界表；每个目录只有一个 owner。
- 首次提交已完成，这是仓库的基线。

远端建立前后都成立的两条底线：

- 合入 `main` 之前先 `rebase origin/main`。
- 推送已 rebase 的功能分支用 `git push --force-with-lease`。

## 2. 提交信息格式

首行写类型前缀加一句话，说清**做了什么**；正文说清**为什么**。

```
<类型>: <做了什么>

<为什么这么做>
```

| 类型 | 用于 |
|---|---|
| `feat` | 新增能力、模块、工具 |
| `fix` | 修缺陷 |
| `refactor` | 不改行为的结构调整 |
| `test` | 补测试或用例 |
| `docs` | 文档 |
| `chore` | 构建、依赖、配置、仓库维护 |

一个提交只做一件事。意见修复与新功能分成两个提交，方便 review 与回滚。

例：

```
feat(transfer): 增加按备注匹配收款人

备注匹配需要先查账户别名，再回落到姓名匹配；
直接模糊匹配会把「房租」这类备注错认成人名。
```

## 3. 远端协作待办

远端仓库、`origin`、首批项目资料和自动检查已经就位。剩余事项：

1. 09-28 全员会确认 02 账单目录由六水改由 Ethan 负责后，再收集团队真实 GitHub 用户名并邀请成员；不要把占位账号写进 CODEOWNERS。
2. 保持私有仓库时，账号升级到支持分支保护的方案后，启用 `main` 保护：必须通过 PR、自动检查通过、负责人批准，禁止强推和删除。若考虑改为公开，先由项目负责人决定是否适合公开项目资料。
3. 规则生效后补入真实 CODEOWNERS，并核对 01、02、06、安全、底座、前端及评测目录归属。
4. 通知全员从远端 clone 或重设 upstream；在保护规则生效前，任何人都不要直接推送 `main`。

## 4. 飞书同步

项目文档会同步到飞书供团队阅读，本地仓库始终是唯一事实源。

- **飞书知识库只放团队阅读层**：工作台、当前版本计划与进度、当前业务 PRD、核心架构契约和协作规则。完整事实仍保存在仓库，不把 `docs/` 当作飞书镜像。
- 发布用 `FEISHU_STATE=.feishu_state.publish.json python tools/feishu_sync.py publish`：
  读 `tools/feishu_publish_all.py` 的 `CURATED_SOURCES` 白名单，用**用户身份**建/改文档。必须全程用户身份——应用身份建的文档，
  用户没有编辑权（实测报 `4030004`）。
- 飞书只保留三层正式入口：当前工作台与当前版本、项目 Roadmap 与版本总览、已冻结且跨阶段复用的 PRD / 架构 / 契约 / 协作规则。新增飞书文档时先确认它属于哪一层，再加入 `CURATED_SOURCES`；执行 `plan → publish → mount`。模板和过程稿留仓库或 Drive 归档；退出白名单的旧文档执行 `archive-plan → archive`，不直接删除。
- 知识库对团队可见需要在空间设置里加成员/群（或设组织内可读）——API 无对应
  设置项，属一次性手工操作。
- 同步方向是本地 → 飞书。飞书上被改过的内容不回流，改动在本地提交后重新发布。
- 《01 项目跟踪》使用 `docs/team/当前工作台.md` 作为人类阅读源；发布后运行 `python tools/embed_stages.py` 恢复文末的 v0.3 甘特图。
- 授权产物与状态文件不入库（见 `.gitignore` 的 `.feishu_state*.json`）；发布用的临时
  markdown 落在 `_feishu_push/`，同样不入库，每次重新生成。

### 改图要重新生成，别手改产物

架构图分两层：`*.json` 是图源规格（唯一事实源），`*.mmd` 是从规格派生的 Mermaid。
**改图改规格，再跑 `python tools/spec_to_mermaid.py <spec.json>` 重新生成 `.mmd`。**

飞书画板不支持 Mermaid 的 `block`/`end` 语法——含它的序列图会整张解析失败，连画板块都不会建。
`spec_to_mermaid.py` 因此用 `Note over` 表达分段。新增图表时避开这个语法。

发布后核对：`python tools/dump_feishu_doc.py <doc_id>` 看块结构，确认画板数与链接数符合预期。
