# 2026-10-19 票04导出回归证据

执行入口为`export_regression.py`，复用9项test_app和1项test_export_secrets，再运行新增7个实例。两次均为13 Passed / 4 Failed，4条失败是CSV公式型文本原样导出，归属[Issue #161](https://github.com/DrErwin/hackerthon-bank-agent/issues/161)。报告仅含结果和哈希，响应体及认证秘密均排除。

| 报告 | 解压后sha256 |
|---|---|
| [首次](2026-10-19-offline-export-boundary-initial.json.gz) | 25439BEE422F93B61E519BB3BEE5FB098DBC5EFC4D1247EFB1EBEF5D49779617 |
| [报告器修订后复跑](2026-10-19-offline-export-boundary-reviewed.json.gz) | A140F27AD33D49CF39F8309B9EFCC5423DB02859B26637DF3302B5FC80ED975B |

第二次修订让同一测试的teardown失败覆盖call通过，防止一次测试计成两项；报告器4项单元测试通过。链路结果与首次相同，真实模型调用0次，失败仍如实保留。

来源为远端main ecf90d0加PR #149安全改动，当前本地后端a74f9d5，相关文件哈希保存在原报告。授权与风险为既有平台替身，报告卡片为受控L03夹具，模拟银行流水实际读取。它不证明真实账单L01至L03、生产检测器及页面验收通过。17项是本专项检查规模，未改全集分母。

## 最终返修复跑

Spec要求补已验证明细跨用户下载，已新增独立U2下载拒绝及本人正向对照；Standards要求setup skip保留Blocked，已补测试。报告器单元测试5 passed，最终公开链路18项为14 Passed / 4 Failed。原17项批次作为历史保留，本节18项为当前专项规模，全集分母保持。

最终报告为[offline-export-boundary-final.json.gz](2026-10-19-offline-export-boundary-final.json.gz)，解压后sha256为`F07AC22730C35AAF88D5911BFFEDC0B50DB420A0A38A1FA22EF7F056E024EC5B`。四项失败仍为Issue #161，尚未修复。

## Issue #161 修复后的独立批次

PR #168 合入后独立复验18 Passed / 0 Failed。报告为[修复后复验](2026-10-19-offline-export-boundary-retest.json.gz)，解压后sha256为`036109E268DB504EA01C85EDEA11F19C452D3436832F0B7E4C1FCC5759D32BD0`。本台账的retest_of关联为`2026-10-19-offline-export-boundary-final.json.gz`，原报告完整指纹`F07AC22730C35AAF88D5911BFFEDC0B50DB420A0A38A1FA22EF7F056E024EC5B`。关联写在本台账，原始JSON未新增retest_of字段；历史报告保持原样。

本地后端 `be771bb` 以 main `e43765a0dec7737a64fd235e3a65c21a0b265656` 的API及风险输入文件更新，另含 PR #149/#165 安全声明修复。本专项风险及授权回调是平台夹具，未消费声明修复或真实检测器。runner、测试及service的实际sha256在新报告中，未将本地组合标记为纯main检出。模型调用仍为0次。
