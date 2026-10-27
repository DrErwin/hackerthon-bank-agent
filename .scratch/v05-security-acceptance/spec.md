# v0.5 安全分层验收

Status: in_progress；01固定96批已交，02实测3 Failed/9 Blocked待审/整改，03为后继独立票
Owner: Erwin；Codex 按本轮授权实施
Directory: `evals/security/`
Package: [v04-security/packages/01-detector-and-coverage：检测器与评测完整性](../v04-security/packages/01-detector-and-coverage.md)

## Problem Statement

现有96条中文判断集（原56+扩40）全部NOT_RUN。旧56脚本限制分母，B/C旧入口仍有硬门和旧规划器包装层，不能直接据其声称真实模型验收通过。

## Solution / Core scenarios

1. SA01：当前96条固定一次模型独立判断，保留risk48/benign24/unclear24、dev68/check28与四维度错误分布。
2. SA02：真实危险检测与可信输入、模型提案、实际裁决和零未授权银行副作用分别观察；ReplyOnly不能虚构成资金BLOCK。
3. SA03：工具备注、用户资料和记忆实际送达模型边界后，核对授权、数据隔离和零未授权副作用；缺能力仍具体Blocked。

## Implementation Decisions

- 01只做分类运行器与离线验证，再用本机已配置glm-5.3 Coding Plan运行一次96条。不得打印或复制密钥，不切模型/入口，不重试调参，不比较模型。
- 分类提示只含统一定义和完整input；expected/id/split/family/维度/顺序不入模型。多轮与不可信来源channel保留，绝不写成系统授权。
- 固定prompt和随机种子，实际请求/响应计数与摘要、原始脱敏回复、usage/费用可得值留证；无法解析或服务错误为ERROR并保留在分母。
- 不改原96条、旧56脚本或138/295/357历史分母。结果先写仓库外唯一新路径，再可复现压缩归档。
- 02、03各自独立票/分支/PR，仅evals/security；先利用现有可信接缝，缺目录外能力向中控交具体依赖，不删硬门。

## Testing Decisions

01先离线验证完整输入、标签不泄露、严格格式与ERROR分母、原始回复脱敏和输出不覆盖，再真实运行。02先四个检测实例各一轮加正常/未知对照，必要时完成既定12轮；其余27轮逐项Blocked。03先三类来源各攻击+正常一条，检查真实收件及独立副作用。真实页面截图由中控等待浏览器恢复后统一采集。

## Out of Scope

生产资金安全门通过、去夹具/未知放行政策、新模型/模型比较/付费提额、旧失败改写、关闭#160、比赛资料或真人安全接受。

## Further Notes

2026-10-27：中控明确批准01→02→03执行。现数据SHA256 `d5bc3c711d4173cbf0ae8ef6c8fc68f8439d6de7ad59e67a0485a06ae633cd53`，24族均2/1/1、ID/input唯一、全NOT_RUN。check缺信息套取/注入保留族，不能称完整四维盲测。

当前B的13实例39轮在live runner无条件gate；MAT传真实planner仍未实现。当前平台已有untrusted_data和resource_load，但旧transfer RecordingPlanner未透传它，C仍需评测侧接线；资料外发的环境出站政策不能用拦截桩代替。以上仅只读核查，尚无本批真实模型调用。
