# 新隔离P01页面环境准备（2026-10-29）

依据根任务本轮明确委派，续 `v05-cross-e2e/02`，只准备隔离fixture与服务。
源为已有根工作树 `demo-pr-merge-20261027/hackerthon-bank-agent`，提交
`17f7ef2c2f2021c866ca4e1f1ce7757d31bace0b`；backend树
`d6bd13c9aeb3a9fc0431920462ed3b02dad4132f`，frontend树
`3fe1279c8e17b7e3b59ee441949958085f556cd4`。生产路径与该提交diff为空。

## 当前接手入口

- 用户页：`http://localhost:5200`；新API：`http://127.0.0.1:5201/api/v1`。
- 根计划先使旧银行所有任务终态，再用localhost:5200用户页、127.0.0.1:5200管理员页。
  Cookie按hostname共享，端口不构成独立cookie jar；本准备没有登录或设置cookie。
- 新轮次：`ui-goals-20261029-1c7aedbe7f42`。
- 全新银行目录：`C:\Users\57652\AppData\Local\Temp\ui-goals-20261029-1c7aedbe7f42-2807j68q`。
  由mkdtemp新建，未复制或清空任何旧银行。

## 初始事实

下面是启动时通过公开gateway读取的初态，非后续用户业务效果；确切时间及字段见
[setup.json](setup.json)。复用已受测的 `session.py` P01初始化：公开BankAccount种子
A1=500000分，及 `evals.cross.case_runner.seed_case`。没有调用会复制私密配置的
`prepare_case`，没有直接写业务DB或执行资金动作。

| 事实 | 实际初态 |
|---|---|
| A1账面/可用/冻结 | 5000元 / 5000元 / 0元 |
| A5账面/可用/冻结 | 0元 / 0元 / 0元 |
| 本月养老金 | `SEED-A1-20261001-cross-pension`，2026-10-01，入账5000元 |
| 已签约 | sub_001=25元、sub_002=39元、cross_keep=20元均active；sub_003为种子中的cancelled |
| 家人收款人 | 已保存A4存在 |
| 银行限额 | 单笔/当日剩余均50000元 |
| 在途 | gateway.wait_for_inflight(0.0)=true |

通用canonical账户种子A1=60000元，本批明确使用既有P01的5000元fixture，并非向
旧银行补余额。账户初态与5000元入账流水均为初始化资料，不是本轮实际发起的存款/转账。
只有根随后真实完成获批2500元到A5、1000元到A4且无其他支出时，才可在实际回读后
称A1剩1500元；本准备没有宣称已执行或已留存。

子进程显式启用 `BANK_PENSION_DEMO_PROFILE=p01-marked-demo-v1`，沿已批准有限
演示事实；没有扩检测、白名单或把未知标安全。原私密配置仅在API子进程内读取，
不打印、不写副本、不改.env。origins仅新前端localhost/127.0.0.1:5200。

## 服务与确切启动签名

均用 `Start-Process -WindowStyle Hidden` 启动并保留运行，无exec会话ID。
当前实际监听API PID **135144**（venv启动器PID **52124**），前端PID **130664**。
三进程的实际ExecutablePath、CommandLine、父PID、创建时间及命令SHA256在JSON中，
只查询上述新进程，没有操作原5190/5191。

```text
D:\hackerthon-bank-agent\backend\.venv\Scripts\python.exe -u C:\Users\57652\.codex\worktrees\demo-pr-merge-20261027\hackerthon-bank-agent\.mnemon\v05-ui-goals-20261029\serve.py
"C:\Program Files\nodejs\node.exe" C:\Users\57652\.codex\worktrees\demo-pr-merge-20261027\hackerthon-bank-agent\.mnemon\v05-ui-goals-20261029\frontend.mjs
```

以上是本次启动记录，不是要求重跑初始化。前端从17f根工作树读取源，依赖只读复用
既有bank-frontend-design-system目录的node_modules，缓存位于本批忽略目录；没有启动
另一个工作树、安装包或改生产配置。real-api模式代理5201。启动前两端口均确认空闲。

临时启动器、原控制台及只读初态保存在本树忽略目录
`.mnemon/v05-ui-goals-20261029/`，所有顶层文件的交接时SHA256见JSON；日志会随根后续
操作追加，该hash只代表交接快照。

- serve.py SHA256：`dc27127e9a34d678dce322412366155827337d6133ebcf012cf21dee0d3da6f7`。
- frontend.mjs SHA256：`e140d9e47f5f5c5bb95268605768daf65540ad2865cd5f68ed193927fd803f6b`。

## 就绪范围

未带cookie的GET检查：前端index、入口TSX及CSS转换200；API/session与前端代理
/session均401 AUTH_REQUIRED，所有检查无Set-Cookie。仅证明服务、静态模块和代理
就绪；没有创建会话、调用模型、操作浏览器或执行用户资金业务，不能记为页面/API
业务/P01通过。原bank目录、5190/5191进程、原用户聊天及D盘脏主目录均未改动。
保留新两服务供根走实际页面与模型；本准备不提交PR或修改生产源码。
