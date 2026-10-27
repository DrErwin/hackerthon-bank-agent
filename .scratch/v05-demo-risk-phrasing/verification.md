# 常见转账语序修复：本地证据

Ticket: [v05-demo-risk-phrasing/01：常见转账语序保留既有演示风险边界](issues/01-normal-transfer-phrasing.md)
Date: 2026-10-27
Base: `90d05fe5110240b54bbddcb25eed2336d349480e`
Branch: `codex/v05-demo-risk-phrasing`
Status: implemented；两轴审查、合入和整体真实页面验收待中控

## Before / After

先加回归再改实现：新语序组 13 failed / 65 deselected。其中原“转账500元给妈妈”明确在真实 `DemoSecurityPolicy.assess_risk` 抛 `RiskFactsUnavailable`；其余新语序亦失败，旧小数语句仅因版本断言尚未递增而失败。

修复后同一文本文件 **78 passed in 3.23s**。原测试保留，新增35节点，含完整语序、礼貌前缀、已有账户、元/块/块钱、全角与两位小数、标点补充；危险前后缀分别有/无夹具均 HIGH；否定、未知内容、未知对象及非法小数保持未检查并暂停；新收款人事实覆盖熟悉收款人夹具，仍 MEDIUM；无夹具暂停、异常不回退。

## 组合回归

解释器复用已有安装，`PYTHONPATH` 指向当前隔离 worktree 的 `backend/`，不会导入主工作区源码。无新依赖，无共享演示库操作。

```powershell
$env:PYTHONPATH=(Get-Location).Path
& 'D:/hackerthon-bank-agent/backend/.venv/Scripts/python.exe' -m pytest app/security app/agent_platform/test_risk_inputs.py app/agent_platform/test_local_demo.py -q --tb=short --junitxml=../.scratch/v05-demo-risk-phrasing/security-results.xml -o junit_family=legacy
& 'D:/hackerthon-bank-agent/backend/.venv/Scripts/python.exe' -m pytest app/agent_platform/test_demo_risk_wiring.py -q --tb=short --junitxml=../.scratch/v05-demo-risk-phrasing/wiring-results.xml -o junit_family=legacy
```

- 安全目录 + 可信输入与本地演示：**518 passed in 55.41s**，见 [security-results.xml](security-results.xml)，SHA256 `f99b164d6dba185f297b266843e17188125110c87435ddaf3f29448cfbcbdc84`。
- 实际装配定向：**10 passed in 17.55s**，见 [wiring-results.xml](wiring-results.xml)，SHA256 `d09750bbe6161216e2feea97e22e19a676df418d62de776b57bbcb99a390b1d6`。
- 合计 **528 passed / 0 failed / 0 skipped**；单文件78项为其中子集，不累加。
- 仓库链接脚本、`git diff --check` 通过。提交前已 fetch，`origin/main` 仍为上方基线。

## 边界

本票只是有限普通语序缺口；演示参数匹配仍由既有平台装配负责，文本单测注入显式演示夹具，不据此声称来源真实完整。真实有限检测优先、原事实覆盖规则、安全门、确认、验证、权限及审计未修改。执行级测试沿用既有受控规划器与隔离银行；本轮未调真实模型、未启动真实浏览器、未运行后端全量，CI 尚无通过结论，真人安全接受未发生。原真实页面暂停证据原样保留，#160 去夹具与三档真实验收未完成。
