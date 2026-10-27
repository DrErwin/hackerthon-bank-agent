# 平台19 来源验证

实现与首次受测归档 `916afb8be965b4e7eae6fe958255c1dbca8bf1a2`；缺失关联补修后 `bdd694869cbcd4a0ba1aec69876aabfb6f036b72`。实现仅平台；所有银行均临时隔离，模型为明确脚本替身或未调用，未重新运行真实模型。

- 原11项 **11 failed /21.24s**，明确显示只拿到子请求/marker、丢父跟进、错误关联未拒绝、F10没有捕捉文本。[原XML压缩](evidence/2026-10-27-platform19-before.xml.gz)，解压SHA256 `7cf5ffbc4a593b2270c574aa21db81338aa066f460015bc0e47ec23da482b24f`。修后同11项 **11 passed /15.45s**，独立小批，不与后续加总。
- 新真实dispatch两项最初 **2 failed /11 passed，15.69s**，银行零写断言处缺测试 `connect` 导入；实际危险BLOCK/普通确认断言均已到达。此为测试搭建错误，不当产品失败；[原XML压缩](evidence/2026-10-27-platform19-dispatch.xml.gz)解压SHA256 `76c68942a9296391b5950e70a059223a8c120a263b88a38a98a345645a91aecd`。修测试导入及加foreign/缺源后，新来源与已有风险/演示/子派发四文件 **47 passed /57.51s**，源码与916afb8b一致。
- 再核真实API可能同时失去关联和context parent，追加该例 **1 failed /5.65s**，不能回退内部marker。[红XML压缩](evidence/2026-10-27-platform19-link-source-before.xml.gz)，解压SHA256 `3e6dac87a67c53a1dbaceb7252842f2e41eb1400e19c993479d60982a5702df1`。
- 补child step失源拒绝后，同四文件最终 **48 passed /0 failed，61.76s**，源码与bdd69486逐字一致。[最终XML](evidence/2026-10-27-platform19-final-affected.xml)，SHA256 `96257146b9aee6c2160ac6f9693b779051c2ba60199e21b61cf30307747ecf7a`。含18来源新例、已有30例，不把递进批次重复相加。

真实dispatch反例使用真实Harness、持久relation、参数快照、有限真实文本检测、安全门及MockBank：父危险原话得到BLOCK、普通原话仍确认等待，银行操作均0。其他例覆盖精确父请求、父子跟进持久重开、hash不回显原话、主体/关联/step/plan/原话缺失及只读来源失败暂停。两项原测试搭建错误均归档，不隐藏，也不借此宣称资金或页面验收。

`request_source_task_id` 是风险来源说明；原operation/revision/ref参数绑定、确认和验证不变。旧P01批次只读保留，不回填未捕捉的历史F10；后继profile实际验收用新批。新增限定演示事实需20/21另票消费，虽本人已批准具体两笔，本票并未新增事实或语法白名单。

## 独立审查后的重放修补

Spec在 `1299c35b` 发现：文本捕捉还被误插入 `handle_message`，其中没有 `response` 变量，会影响已有任务原请求重放。新增两项先实际 **2 failed /6.32s（NameError）**，[原XML压缩](evidence/2026-10-27-platform19-replay-before.xml.gz)，解压SHA256 `7d4bbd09d7a50b3402c9ea973e88b1c57b6d98a4dda7e532bf90a7cb6d348e06`；旧48项不覆盖该分支，不能作为最终绿色结论。

实现 `5ac1727144d6d5c3736612365f5de6b453228c0a` 完全移除误块，捕捉只留正确普通 `_resume` 路径。五文件（上述四文件加既有 `test_harness.py`）最终 **88 passed /0 failed，61.75s**，[最终XML](evidence/2026-10-27-platform19-replay-final.xml)，SHA256 `fdbd182988937870ab903207afb914e774607a5b0bac671b1e1b42f5bc765a55`；含20来源/重放新例与68既有例，不与此前递进批相加。

Spec增量及Standards独立审查均0剩余必须项，均只读原证据、未复跑。CI另核；完整集成、页面、真人安全接受不在本票局部结论内。
