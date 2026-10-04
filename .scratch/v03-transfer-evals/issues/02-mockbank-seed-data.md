# 02：模拟银行测试种子数据解耦与评测数据扩充

Ticket ID: v03-transfer-evals/02\
Package: [transfer-agent-framework/packages/03-v03-evaluation：v0.3 评测与专业审查](../../transfer-agent-framework/packages/03-v03-evaluation.md)\
Spec: [普通转账评测规格](../spec.md)\
Type: task\
Status: resolved\
Owner: Erwin\
Directory: `backend/app/services/`\
Blocked by: v03-transfer-evals/01（需依据 01 规划的数据依赖设计）\
Unlocks: 03

## 业务目的

将模拟银行目前硬编码在 Python 代码中的测试数据彻底解耦为独立 JSON 文件，并扩充同名联系人、临界余额账户等评测种子，使系统具备支撑 151条场景、153个独立样本正交评测的数据底座能力。

## 交付

- 在 `backend/app/services/mock_bank/seeds/` 创建独立的种子数据文件：
  - `accounts.json`：定义预置银行账户数据及余额；
  - `payees.json`：定义预置收款人通讯录数据。
- 改造 `backend/app/services/mock_bank/core.py`：启动和播种时从 `seeds/` 读取装载，移除硬编码字典常量。
- 扩充评测所需的种子数据（保持与既有 A1/A5/U2A1/A2/A3/A4/A7 100% 兼容）：
  - 增加两个同名收款人：`A8: 张伟（工行，尾号1111）` 与 `A9: 张伟（招行，尾号2222）`；
  - 增加同名同行多卡收款人：`A10: 李明（卡号尾号3333）` 与 `A11: 李明（卡号尾号4444）`；
  - 增加纯手机号收款人：`A12: 赵强（手机号 13812345678）`；
  - 增加临界余额账户：`A6: 可用余额恰好 50,000 分（500.00元）`；
  - 增加受限状态账户：`A8_ACC: 状态为 frozen`。
- 补充并运行数据加载与新种子查询的单元测试。
- 仅修改 `backend/app/services/` 目录，不跨目录修改评测文件。

## 验收

- `MockBankService` 正常从 JSON 文件装载种子数据，原有 269 项后端测试与 14 项 mockbank 评测无损 100% 全部通过。
- 新增单元测试证明：能够成功按姓名检索到两位“张伟”、按手机号检索到“赵强”、正确读取 A6 临界余额。
- 独立 PR，通过仓库静态检查与双轴 AI 审查。

## 2026-10-04 执行记录

用户明确调用 implement 完成本票。执行人 Codex（Erwin 工作线），独立 worktree `codex/transfer-evals-02`，基线 `9df2c78`（PR #48 已合入，前置01已resolved）。实施仅在 `backend/app/services/`；票据与项目跟踪是单独过程记录。

当前兼容决定：默认账户保持 A1/A5/U2A1，新评测账户通过 `seed_demo(include_evaluation=True)` 显式装载到隔离银行库，保持14项既有评测的账户集合断言。新增联系人来自JSON。D2 的 closed、类别和历史额度由03复用已有银行存储装载，不在本票追加全套故障前置。源码 / editable 运行方式保持不变；wheel 打包 JSON 需后续构建目录票处理。


交付提交：`f79daffc7e74f10d9af0b2d525b748c68e647027`，分支 `codex/transfer-evals-02`，独立 [PR #50](https://github.com/DrErwin/hackerthon-bank-agent/pull/50)。新增数据与银行相关测试22项通过；全量回归和CI待核对。独立 Standards AI / Spec AI 审查均0问题；没有真人批准或合并证据。


最终本地验证：独立测试环境按 `backend/pyproject.toml` 安装，后端全量 **273 passed**（原269+新增4），模拟银行 **14 passed**；新增数据与银行相关测试 **22 passed**。差异空白、services Python语法、仓库链接检查（排除本机第三方虚拟环境）通过。PR已转为ready，待远端检查与负责人审查/合入；03依赖能力在PR合入后才满足，不能以本地测试替代合入证据。


远端 CI：[Repository checks #37136708029](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/37136708029) 已成功，检查对象为PR #50提交 `f79daff`。本票状态 `in_review`（实现、验证、双轴AI审查已完成，待负责人审查/合入）；不记为已合入、真人批准或v0.3验收。下一步审查/合入本票，再执行03。票据与项目跟踪仍为本地过程记录，未混入services代码PR或同步飞书。


2026-10-04：用户明确授权合并。PR #50 已squash合入，主线提交 `baca81233e725ee1d1d47fa8020a8acb5ff4221d`；本票resolved，03实现依赖已满足。用户本次合并授权不记录为Ringo个人批准；无安全策略/资金执行逻辑变更。
