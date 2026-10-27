# 子任务暂停的父卡说明：票 12 最小规格

Status: implemented_pending_review
Owner: Erwin（v0.5）；执行 merge_standards_review 子代理
Accepted by: Erwin，通过非比赛资料任务授权与中控明确分派
Accepted at: 2026-10-27
Package: [v05-cross-linkage/packages/03-cross：三个生活目标编排](../v05-cross-linkage/packages/03-cross.md)
Directory: backend/app/modules/cross/

## Problem Statement

真实 P01 首笔转账子卡公开说明安全核对未完成、尚未提交银行，父卡却将所有 needs_attention 都汇总为“办理结果未知”。用户因此无法区分暂停原因。原记录为根代理 `.scratch/v05-control/http-completed-2026-10-27.md` 的 P01 段及原批 `http-live-d7818f4d3f04`，子任务 `8e81532e-5e25-4fb9-9ddc-6fda58e686de`、操作 `8f206efe-161d-4fd4-bb3d-885537b225b1`；只读保留，不回填历史。

## Solution / User Stories

1. PC01：用户看到父卡明确“已暂停”，并能读到原子任务已有公开、脱敏的具体说明。
2. PC02：真实银行结果未知时，子卡原有未知提示、原任务和原操作查询继续保留；父卡不凭状态或缺少 operation 推断是否提交。
3. PC03：父子状态、确认、动作、重试、安排占用及继续/停止路径保持原实现，只改变暂停汇总提示。

## Implementation Decisions

在既有共用暂停展示分支只读取当前用户、轮次下原子任务的已持久公开结果 message，父卡复用该说明。沿用已有公开存储查询，不复制安全分类、不新增契约、不解析错误或银行内部字段。公开子任务缺失时仅引导查看对应任务说明，不猜测资金结果。

## Testing Decisions

基线 main `35fd849d4aeb586bf7bc349b52ae7bf9eb42d107`。复用既有本人账户安全暂停、养老金 P06 未知、通用 HTTP 原号查询/叫停回归；仅补充已有用例对公开说明来源和暂停语义的断言，不新增文案镜像测试。先以原实现核对目标语义断言，再运行既有养老金文件及通用 HTTP 控制文件。使用新临时库及既有脚本/本地银行装配，无真实模型、浏览器或原批银行重跑。

## Out of Scope

不改资金事实、公开状态、允许动作、查询/重试/继续/停止、占用、安全或合同；不碰 Cross09 隔离运行工作树、函数、原 XML，不并入其冻结源码。不改父收尾状态计算，不将本票局部回归称为真实 P01 或最终 E2E 通过。

## Further Notes

已核本组 12 未占用，复用附属且干净的旧 Cross 工作树，从最新已核 main 开独立分支。沿用已批准的单票粒度与既有验证接缝；已读取 to-spec / to-tickets / implement 指引，前三项 disable-model-invocation，本会话不声称调用斜杠命令。按其流程手工记录规格、票据及执行，低影响文案依中控要求不新增测试文件。独立两轴、CI 与最终合入交中控，不自合并。

## 实际局部结果（2026-10-27）

原生产实现、仅补既有本人账户用例的公开说明语义断言：两参数 **2 failed / 8.18s / exit 1**，均实际得到父卡“办理结果未知”。[原始红例 XML 的无损 gzip](evidence/2026-10-27-paused-summary-12-before.xml.gz) 解压 SHA256：`409b59b3f31f5cca73fe0d90dc4e276b19eee63499555c128e9bcbad86fadffe`。压缩后已校验与原 XML 字节相同，保留失败事实。

受测源码 `e0eae1d92d28ce51a0e5307c574055c5e7b05d24`，base `35fd849d4aeb586bf7bc349b52ae7bf9eb42d107`；测试运行期间 backend 无差异。backend 树 `5ccd58b3260d0dbc71fceb002c66fc3e2ac80dca`，Cross 树 `effe087e37897f0f4f9aed17d0c765f3cd8fe3e3`。

一次运行 `test_cross_pension.py`、`test_pension_contract_inputs.py`、`test_task_controls_http.py`：**23 passed / 0 failed、error、skipped / 56.47s / exit 0**，XML 共 23 个唯一测试。包含本人账户安全暂停的两参数、P06 未知及安排保留、通用 HTTP 原号查询、未知后叫停及核实后停止且不新建第二笔。仅补充三个既有用例的语义断言，资金结果与调用次数断言保留，无新增测试文件。

[原始通过 XML](evidence/2026-10-27-paused-summary-12-after.xml) SHA256：`12757c8f693bbea6885f3187fe2cf5fa2cfc375142ca2b3d55086a439bd55ab5`。该证据为隔离临时库的既有模块/真实本地 HTTP 装配回归，含脚本替身，不是本轮真实模型、原 P01 或页面验收。原 P01 观察与 Cross09 冻结源/原 XML 保留。差异空白通过；两轴、CI 和合入仍交中控。
