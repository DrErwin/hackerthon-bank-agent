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

原进程结果：**393 passed / 13 skipped，453.95s，exit 0**。未终止或重复启动；13 个已有端点 skip 不计通过。[最终原始 JUnit](evidence/2026-10-27-platform12-combined.xml)，SHA256 `3C9317D7C6CBE9FDBD940B61394C7C1BD8659E70E79FE9E14B0B397BC8FFF78C`。后续仅归档本证据，不改变受测 platform 树；`git diff --check origin/main...HEAD` 另行核对。

以上均是明示替身模型下的本地真实平台/存储/安全/模拟银行组合；不是新真实模型、页面验收或真人安全签核。API 的整体停收、排空、记忆复位和会话失效另票消费，平台没有删除历史任务或伪造总体成功。AI 两轴审查与远端 CI 按最终 head 由中控单列，不以本地通过替代。
