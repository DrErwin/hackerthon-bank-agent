# 票 06 · L01 公共业务运行台账（2026-10-20）

状态：**阶段一部分交付，非完整业务整包验收**。

本次源代码基于 2026-10-20 main 新建，包含来自 `test/bills/public-business-evidence-06` 的四个独立评测文件，保留真实 L01 公共链路验证逻辑；不包含其旧版本的来源绑定报告。原票据 [06](../../.scratch/v04-ethan-bills-backend/issues/06-full-business-eval.md) 原始 17 场景 SHA 和各笔真实银行检查仍保留在其历史分支。

**2026-10-20 新基线实际运行已完成**：被测源码 [`c2e8f3ea2949c32bf4526b426f647e6c03f69f5c`](https://github.com/DrErwin/hackerthon-bank-agent/commit/c2e8f3ea2949c32bf4526b426f647e6c03f69f5c)，真实 [Actions 39425788637](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39425788637) `success`，Python 3.12.15，调用 `run_business_evidence.py --revision c2e8f3ea2949c32bf4526b426f647e6c03f69f5c`，结果 **17 collected / 17 passed / 0 failed / 0 skipped / 0 errors**。133 份源码 Git Blob 与源提交逐字节校验、44 个导入模块证实来自已核验的源码、17 例均核对银行表/余额与资金副作用。

- [原始 gzip](evidence/2026-10-20/20261020T125347038226Z-python3.12.15-public-l01-phase1-c2e8f3ea2949.json.gz)：压缩 SHA256 `d20344c52797da7a27a3e20ee722ac111e7f6c96cd294ac2f3d04b56db03dac2`；解压 JSON SHA256 `0436531856dd59bf47126d5585442caba00a9d35146b8beaa2770828069111fc`；二进制 Git Blob `1fc78728f928356f30d7bc26a230d37dc808cede`。这是 Actions 真实生成文件的原始字节，由编号日志块恢复，未复写执行时间或逐样本结果。
- `summary` `17 passed` 表示17个场景的**业务断言结果符合预期**；含预期拒绝/等待/取消，不是17笔业务全部 succeeded。
- `overall_status=partial` 和 `full_ticket_acceptance=false` 保持原样。其余 L02/L03、复杂对比、多异常类型、真实模型/React/专业安全仍未全部覆盖；既有96设计不能直接记96实跑。

**范围**：包括 17 个真实 L01 业务场景 + 实际银行不变证明；不覆盖 L02/L03 全路径、真模型、浏览器、安全专业签核。按团队「一张票一目录、一人最多两张未合并 PR」约定独立提审。
