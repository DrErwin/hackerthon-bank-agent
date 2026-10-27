# Security20：局部验证记录

Ticket: [v05-birthday-platform-dependencies/20](issues/20-pension-demo-risk-provider.md)
Spec: [P01有限演示范围](pension-demo-risk-20.md)
Date: 2026-10-27；AI实现验证，非真人最终安全接受

## 来源和受测代码

基线main c760f0d0e490db1bee22b181678ce7e869eb5915。独立分支codex/v05-pension-demo-risk-20，生产文件只增加安全提供方；原demo_text_risk、risk_detector、demo_policy和A2运行时配置未改。

- 实现commit：9f9a95a6（首次完整82项目标测试后提交）。
- 全安全目录实际受测commit：72ffd78977fea05475ece9f3d7d34f41cd81a5ca；该提交只将红例XML无损压缩归档，原字节另保留，不改运行代码。
- 该受测安全目录tree：cda92940c091f1e2cc6224a9cc7996b6feff88b1。
- pension_demo_risk.py blob：88af0fba6565ab2b0eaa0672401abb66ec778c15。
- test_pension_demo_risk.py blob：1eb514a2df8a5ca221616682c5f4f9762e3fd04e。

## 实际运行

使用现有Python环境，PYTHONPATH显式指向本隔离工作树backend，PYTHONIOENCODING=utf-8；没有读写私密配置、调用模型、改共享数据库或绕过执行门。

| 执行 | 控制台结果 | 原始JUnit |
|---|---|---|
| 首个公开函数场景红例，基线+尚未提交的单个新测试，提供方尚不存在 | 1 failed / 6.09s，ModuleNotFoundError | [red.xml.gz](evidence/2026-10-27-security20-red.xml.gz)，无损原XML |
| 增加提供方后的同一首例，当时为未提交工作文件 | 1 passed / 4.33s | [first-green.xml](evidence/2026-10-27-security20-first-green.xml) |
| 扩展到两笔/四跟进/缺源/缺银行/异参/未知/危险与输入不变；提交前工作文件与上列实现blob一致 | 82 passed / 4.78s | [targeted.xml](evidence/2026-10-27-security20-targeted.xml) |
| 全安全目录，commit72ffd789 | 656 passed / 44.87s，0失败/错误/跳过 | [full.xml](evidence/2026-10-27-security20-full.xml) |

命令均为python -m pytest backend/app/security/test_pension_demo_risk.py -q --junitxml=<对应路径>，全目录一轮使用backend/app/security。控制台耗时与JUnit testsuite.time有pytest记账差异，以上耗时是实际控制台值，未改原XML。

| 原始证据 | SHA-256 |
|---|---|
| red.xml.gz | 60e1ac38a732e8117d183090d76862a8f3b7cf6de99269f39ee8de433be3e50d |
| red解压原XML | 6d1dfc56a72ebf6f28ab697fa0fe659049ba344d8015045b5281a06b139c2f16 |
| first-green.xml | 93432e9abb27c7b68cb873fcbd6ef3ffbdc2a66df2b40b28bde127deb6d55b59 |
| targeted.xml | 568d1d636f4f2d0c6801676fc0b8ac96c03726cb37f3c51820f9b6f5d0adde02 |
| full.xml | 046b618779308bc4e28f3f1e76d7a6aa25c103b69d49ee640da7ca3248035f75 |

红例错误正文带原生CRLF，直接作为文本新增会触发diff空白检查；仅用gzip空文件名/mtime=0无损封装，解压字节逐字核对。原XML副本保留在本隔离工作树的外部evidence目录，不做换行修复或重跑替代原失败。

## 证明范围

局部测试的ParentRiskInputsForTest只是明示的来源字段测试替身，不证明可信父子关联；真实user/task/round、source_task_id、原父请求和受控跟进由平台19负责。旧RiskInputs缺字段/默认None不继承模拟覆盖。

两笔精确参数均能得到marked-pension-demo:p01-marked-demo-v1来源，真实NEW_PAYEE保持MEDIUM。未知/损坏银行事实时只返回十二维模拟checked，FAMILIAR_PAYEE/NEW_PAYEE仍未检查，现有政策抛risk-signal-coverage-required。原environment/amount_history的unknown状态未被改为known。危险前缀、后缀和跟进保留原demo-text-risk-5的HIGH优先行为，错误来源/参数也不能隐藏正向危险。其他原话、否定、解释、内部marker或未知附言仍为原unknown；旧A2有限语法/政策回归由全目录656项覆盖。

未改确认、验证、执行器、银行资金规则或默认运行时接线，函数本身不进行资金操作。平台21需要默认None的显式opt-in；只有19/20/21合入后的新隔离实际HTTP/页面/银行案例才能证明P01闭环。旧96分类/B/C观察结果不变，本票未重新运行模型；CI、两轴独立审查和真人最终安全接受另记。
