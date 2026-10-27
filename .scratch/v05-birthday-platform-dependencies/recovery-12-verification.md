# 票12：演示业务时钟与可信轮次验证

日期：2026-10-27。只修改 `backend/app/agent_platform/` 与本组规格/证据。

- `a680055a` 首轮完整平台目录：**378 passed / 13 skipped / 1 failed，419.07s，exit 1**。[原始失败 JUnit 无损压缩归档](evidence/2026-10-27-platform12-failed-utc.xml.gz)保留，不覆盖；解压字节与原文件完全一致。pytest 的 CRLF/内嵌空白未经改写，压缩仅避免把原始失败 trace 当作源码尾空白检查。
- 唯一失败 `test_cross_runtime_wiring.py::test_real_composition_mounts_cross_and_traces_children`：初版业务时钟返回 UTC，原银行/账单使用北京时间月界；scope 的月初不一致。修正 `62bc3372` 让业务时钟默认值与 setter 均返回北京时间。
- 修正后定向 **4 passed，8.52s，exit 0**：上述真实 Cross 装配回归及本票三个组合用例。额外固定 UTC 月末 16:00 在银行/账单/订阅/联动均为北京时间次月 1 日 00:00；setter 不替换各模块持有的 callable。
- 重置后同进程 memory、生日及能力策略读取银行持久新轮次，旧轮次拒绝；重启配置仍为 D1 时恢复银行 D2 和持久业务起点。
- 业务时间前后拨动不改变确认记录或验证码有效期；验证码仅在真实验证时钟到期后过期。确认、验证与网络等待未接入可变业务时钟，有限解冻安全记录使用真实 UTC。

## 最终合并态回归

前置 PR #323、#325 均合入后，本分支 rebase 到 main `0b72b0a1c2ee7a95367a33f25d1a40eeea2cd880`，保留 G3 恢复代码/README 与本票时钟接线。固定受测提交 `cd6a169088d07fe328c28fa5a15b6e03ef202b99`，`agent_platform` 树 `e3310c496db5bf9c9252e7ff63ea685c111c3aff`。

```text
python -m pytest backend/app/agent_platform -q --basetemp=<本worktree专用临时目录> --junitxml=.scratch/v05-birthday-platform-dependencies/evidence/2026-10-27-platform12-combined.xml
```

补修前原进程结果：**393 passed / 13 skipped，453.95s，exit 0**。未终止或重复启动；13 个已有端点 skip 不计通过。[原始 JUnit](evidence/2026-10-27-platform12-combined.xml)，SHA256 `3C9317D7C6CBE9FDBD940B61394C7C1BD8659E70E79FE9E14B0B397BC8FFF78C`。当次归档提交 `f073df1f` 没有改变受测 platform 树；不将这份旧整套结果归到下述安全退役时间补修之后。

## Spec 复审后的安全退役时间补修

- 审查发现受控编辑 `_retire_original` 把业务钟传给安全 `begin_retirement` / `seal_retirement`，污染退役记录及 `security.decided` 时间，而银行退休证明使用真实时间。
- 新增真实 Harness/Cross/安全/银行受控编辑回归：分别将业务日期设为 2031-06-12、2009-07-17，完整走到冻结验证等待后修改。补修前 **2 failed，11.48s**，错误均为安全退役时间取业务日期；[原始红例 JUnit 无损归档](evidence/2026-10-27-platform12-retirement-before.xml.gz)，原文件 SHA256 `D636ED03558D5EBE9EF02B44E64D277789CFCAA86FB6C1CD1F784E32AA107303`。
- 最小补修只让安全受理、封存各自取真实 UTC；业务编辑的 `accepted_at` 继续使用业务日期。新增断言核对 `created_at ≤ 银行 retired_at ≤ sealed_at` 均在真实调用区间内，审计 `timestamp` / `checked_at` 等于封存时间，业务 `accepted_at` 保持前拨/后拨日期。
- 补修后定向命令：`python -m pytest backend/app/agent_platform/test_demo_runtime_clock.py backend/app/agent_platform/test_birthday_edit_handoff.py backend/app/agent_platform/test_birthday_edit_continuation.py -q`，独立临时目录；结果 **58 passed，100.74s，exit 0**。受测 platform 树 `9d4d9670525eb99f2e28bbbf95d76d2729fc3ac4`；[通过 JUnit](evidence/2026-10-27-platform12-retirement-fixed.xml)，SHA256 `B4AAAB766F38063A17B10010AEFFE11FFECD3887730BC3D4259EA54902D81D62`。
- 按中控要求未重跑完整平台套件；58 项是补修后的定向证据，393/13 skip 保留为补修前证据。源码与归档差异分别做空白检查；待独立复审。

以上均是明示替身模型下的本地真实平台/存储/安全/模拟银行组合；不是新真实模型、页面验收或真人安全签核。API 的整体停收、排空、记忆复位和会话失效另票消费，平台没有删除历史任务或伪造总体成功。AI 两轴审查与远端 CI 按最终 head 由中控单列，不以本地通过替代。
