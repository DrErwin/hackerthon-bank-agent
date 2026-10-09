# 03：真实模型入口与报告

Ticket ID: v03-security-eval-integration/03
Package: [交付包03](../../transfer-agent-framework/packages/03-v03-evaluation.md)
Spec: [安全评测接入规格](../spec.md)
Type: 开发
Owner: 用户授权AI接入；Ringo专业审查待记录
Directory: evals/security/
Status: completed（用户批准合入 2026-10-09；Ringo 专业签核未发生，以用户明确豁免为准）
Blocked by: None（02代码已交付并汇入PR链）；实际用例仍须具备对应检测、资源和观察能力
Core scenarios: SI07
Verification: 本票自动断言、故障及缺口反例、相关离线流程；联合验收仍归原票12。
Accepted by: 用户授权AI
Accepted at: 2026-10-07

## What to build

枚举19实例57轮及共享三轮；入口默认离线并支持独立采样，缺检测/资源/观察能力调用前Blocked，报告不可覆盖和秘密不落盘。

## Acceptance criteria

- [x] 枚举19实例57轮及共享三轮；入口默认离线并支持独立采样，缺检测/资源/观察能力调用前Blocked，报告不可覆盖和秘密不落盘。
- [x] 不修改原JSONL、历史模板或后端业务规则；本票代码只落evals/security/。
- [x] 保存真实执行与离线替代边界；未调用付费真实模型，Ringo审查单列。
- [x] 本票专项及受影响核心路径验证、有独立分支/PR和双轴AI审查证据。

## Comments

2026-10-09 用户（项目负责人）明确批准本批 PR，squash 合入 main（#83 → `c840c88`；squash 分叉冲突经 fd526a3 merge 解决，合并后 50/0 复验通过）。Ringo 专业签核未发生，以用户明确豁免记录。本票代码关闭；真实运行（--live-glm）仍未发生，启用前置条件见 progress.md 下一步。

2026-10-09 真实模型入口已交付 [PR #83](https://github.com/DrErwin/hackerthon-bank-agent/pull/83)，代码提交 92d51dc + 审查修复 a5ba300/aacee87，base 指向 02 分支。45项专项测试（终态50）。枚举19实例57轮+共享3轮：可接入8实例24轮默认离线真实执行（D002业务链直连、C001六变体含v03共享缝、P002独立夹具），缺检测器/资料入口/观察端的11实例33轮调用前Blocked。入口默认离线（real_model_calls=0、model_config_read=False、零供应商请求）；--instance/--round 独立采样；报告强制仓库外新路径、拒覆盖；秘密不落盘。审查修复后供应商/型号/端点一律来自 --config 显式配置，代码无硬编码。遗留：--live-glm 首次启用前建议 Ringo 复核 live 判定断言口径；本机无 langchain_openai，完整 planner 构建需在有依赖环境验证；共享3轮功能侧实跑引用待功能侧37轮真实运行后回填。待 Ringo 专业批准。

2026-10-07本轮只交付规格与票据。用户明确要求“只执行到拆票，实施先不做”；本票未领取实施，未写代码、未运行评测。实施须等待用户后续明确启动及前置票交付。缺能力的真实样本须在调用前Blocked，本轮不调用付费模型。
