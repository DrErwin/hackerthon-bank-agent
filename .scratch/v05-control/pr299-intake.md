# 预算API02 / PR299中控接收记录

Date: 2026-10-25 19:09（Asia/Taipei）
Status: delivered / reviewed / merge_not_approved；不代表真实采用预算或E2E已完成。

## 固定交付

- [PR299](https://github.com/DrErwin/hackerthon-bank-agent/pull/299)，Draft，base=main；head `d262bb19ed6f52cc26728f31c8fdfdcc79224972`。
- 票为[v05-budget-adoption-origin/02：API可信F10来源](https://github.com/DrErwin/hackerthon-bank-agent/blob/d262bb19ed6f52cc26728f31c8fdfdcc79224972/.scratch/v05-budget-adoption-origin/issues/02-api-f10-origin.md)。唯一实施目录`backend/app/api/`，其他仅本组票/审查/证据；未改storage、platform、cross、contracts或共享进度。
- 作者对话“补齐个人预算采用记录与版本存储”，`01a171b0-4bf1-7571-bf2c-7c85c404329d`；独立worktree `C:/Users/57652/.codex/worktrees/v05-budget-f10-api/hackerthon-bank-agent`，分支`codex/v05-budget-f10-api`。
- 作用：F10专用采用来源/历史查询与精确原请求恢复；普通聊天或resume不能自报来源；任务结果与历史HTTP回执分别保存。预算输入事件整批原子发布，避免回执丢失后拼接新旧事件。

## 中控实际核对

最终受测提交`355ea4ed981764149ed03c1d2bc4007366efc7db`，main代码基线`2a070b9cf992a109d8b54718a49dc3e3b56bd236`。交付head与受测backend树同为`641a9d2abc85419506f32294ad4e238c60c6dc0c`；2a070b9到中控c02c70d仅文档变化。

| 层级 | 原始结果 | 边界 |
|---|---|---|
| 新API真实TCP HTTP | 23通过 | 预算业务/规划是持久替身；此组银行操作/交易为0，不证明真实AdoptedBudget写入 |
| 平台来源回归 | 35通过 | 固定可信来源、原请求与受控恢复 |
| 相关API回归 | 35通过 | 父子7、派发10、配送3、验证故障7、订阅2、原app6；含既有隔离模拟银行用例 |
| 最终合计 | 93唯一节点，0失败/0错误/0跳过，96.15秒 | 定向回归，不是完整后端、真实模型或React页面E2E |

中控直接读取已提交的[summary.json](https://github.com/DrErwin/hackerthon-bank-agent/blob/d262bb19ed6f52cc26728f31c8fdfdcc79224972/.scratch/v05-budget-adoption-origin/api02-evidence/summary.json)，复算13份证据文件SHA256及3份gzip内原日志。`rebased-final.xml`直接解析为93个不重复测试节点；XML SHA256=`463fff503ad73fde0e98f5462c5372df7e6f8682bc01dc02009cdb52fc70295a`，原日志SHA256=`6c11473bb3a99e1d2c58b0416cf5b30d0ba74f393c0179caab3071e61de066df`。中控未另跑测试；初版21项、修后93项及同步后最终93项各自保留，不合并冒充一个批次。

规范/规格两位独立子代理的实际活动已读取：[审查记录](https://github.com/DrErwin/hackerthon-bank-agent/blob/d262bb19ed6f52cc26728f31c8fdfdcc79224972/.scratch/v05-budget-adoption-origin/api02-review.md)。规格初审发现逐事件INSERT IGNORE可能在已发布且回执丢失后混入新交互；修订8a9b6c9用固定task_updated标记保护完整事务批，最终两轴0剩余必须项/0建议。AI审查不等于Erwin本人批准。

CI按准确head读取：run `40186857482`，check `121149381543`，注释为账户计费/额度导致任务未启动，记**Blocked**。第二批五项的本地验证例外没有覆盖299。

## 已分派的下一步

原API/storage对话已接收mainc02c70d + PR293@`7c2fe00e0c297b3c81709f4853501f3563120245` + PR299@`d262bb19ed6f52cc26728f31c8fdfdcc79224972`的隔离组合核对，只应用各自补丁，不重复298或第二批祖先，不加入296/294/291/290或生日新政策。

只运行API93及有意义的293采用版本/CAS/回退/同应用库相关定向，保存原始日志、JUnit、导入来源、代码/环境及散列，经双轴审查回交自有组合材料。不得在混合验证分支修产品代码或改期望；发现问题交原目录。现有E2E使用原固定代码/数据，新组合使用全新绝对config.data_directory；不迁移共享库。

组合完成后才形成293+299具体合入材料，另请Erwin裁定合入及本批CI例外。v5→v6不能只回滚代码，任何共享库迁移仍须一致性备份与原操作恢复方案。当前没有该批准；cross06仍等存储/API实际合入和中控开始信号。
