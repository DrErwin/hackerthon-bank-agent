# Fresh就绪核对：养老金筛选勘误

原restart-readiness.json SHA256 `552d1e133b8eedd39754ed777873b3b601a3bc147cf9ade33209388d6861cd05` 与原MD `712795efc25d44068524ed4823c2fd867b7d495e4db2427b539824504081f494` 保留不改。原布尔false是观察者查询误用category=pension，非缺养老金或重复播种；原JSON中exact_pension_seed_rows已保存正确的单条500000分记录。

按原serve.py:52-58合同重新只读：本人A1、当前2026-10月份、counterparty_id=PENSION、direction=inflow精确1条，金额500000分；transaction_id=SEED-A1-20261001-cross-pension，nature/category均transfer是合法原值，未伪改分类。采样窗口 2026-10-29T14:43:28.178803+08:00 至 2026-10-29T14:43:28.225594+08:00，source `ffa42936c172f3114fa0a826f99ea4373f39058a`。

当前A1账面/可用5000元、A5为0、冻结均0；3项active；银行操作/冻结/订单/付款全0，应用tasks/api_tasks/jobs/security_executions/challenges全0，model.started/finished审计0。新正确口径下全部检查=True。初态依然未办业务，不能标P01/页面PASS。

两库mode=ro/query_only显式只读事务，total_changes bank=0、application=0；未调用HTTP/runtime/check/模型/浏览器，未读OTP/密钥/配送原文。原setup与initialfacts hash不变。此文件仅审计筛选勘误，不新增业务事实。JSON SHA256 `9f19ffe49a70f9de62e04d8dbaabba4d6ae8f463e15ad18fd57bbcfc222cecb1`。
