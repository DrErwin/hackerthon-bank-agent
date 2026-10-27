---
name: 银行助手设计系统
description: 对话带路、卡片选择，手机优先的银发银行助理
colors:
  background: "#F5F5EF"
  foreground: "#272A25"
  card: "#FFFFFF"
  primary: "#A54218"
  primary-pressed: "#853512"
  secondary: "#F0F1EA"
  muted: "#EDEFE7"
  muted-foreground: "#5A6257"
  accent: "#FBEEE5"
  success: "#356447"
  destructive: "#A42B28"
  warning: "#825B12"
  border: "#89927F"
  line-soft: "#E0E4DA"
typography:
  body:
    fontFamily: '-apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Noto Sans SC", "Microsoft YaHei", sans-serif'
    fontSize: "1.125rem"
    lineHeight: 1.55
  title:
    fontSize: "1.25rem"
    fontWeight: 700
    lineHeight: 1.35
  label:
    fontSize: "1rem"
  amount:
    fontSize: "2rem"
rounded:
  control: "12px"
  card: "16px"
spacing:
  xs: "4px"
  sm: "8px"
  compact: "12px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.card}"
    rounded: "{rounded.control}"
    padding: "12px 20px"
  button-primary-hover:
    backgroundColor: "{colors.primary-pressed}"
  button-outline:
    backgroundColor: "{colors.card}"
    textColor: "{colors.foreground}"
    rounded: "{rounded.control}"
  input:
    backgroundColor: "{colors.card}"
    textColor: "{colors.foreground}"
    rounded: "{rounded.control}"
    padding: "12px 16px"
---

# 银行助手设计系统 v0.4 · 全流程对话驱动

2026-10-26。适用用户前台；管理演示台保留原有信息密度。记录已建立的系统，业务能力以现行接口为准。

## Overview

对话是主界面，业务卡片是助手提供的可操作回答。助手用一句话引导当前步骤，用户通过点选或打字推进同一件事。资料、状态和下一步留在当前对话里。

暖白底、深色文字、深橙操作色，配中文系统字体与 Lucide 线性图标。用留白、标题和列表关系解释内容，减少框套框、重复标签及次要说明。表达简短、亲切，先说发生什么，再给下一步。

- 输入框常驻；工具、记录和当前事项随时可找。
- 每次一个决定：选择用列表，填写用表单，核对用清单，结果用回执。
- 手机优先，电脑沿用同一办理顺序和状态。

产品约束见 [PRODUCT.md](PRODUCT.md)。本文件维护视觉和交互共性，不代替业务规格或验收记录。

## Colors

主色用于动作、选中与焦点；中性色承担阅读和分组。上方变量与 [design-system.css](src/design-system.css) 对应，既有 shell 通过语义别名共用。

| 角色 | 使用位置 |
|---|---|
| 深橙 primary / primary-pressed | 主按钮及其悬停状态、关键入口、焦点 |
| 浅橙 accent | 选中对象、轻量提示及次级动作悬停 |
| 暖白 background / 白色 card | 页面与表单、业务卡片、抽屉表面 |
| 深字 foreground / 次字 muted-foreground | 正文与金额 / 日期、说明、辅助标签 |
| secondary / muted | 次级按钮和低强调表面 |
| border / line-soft | 输入与可点区域边界 / 列表内部轻分隔 |
| success / destructive / warning | 完成 / 明确失败、字段错误 / 待核实与关注 |

状态必须同时有文字或图标，颜色只作辅助。金额保持深色，收支方向由文字与图标表达。正文对比度目标至少 4.5:1，交互边界与焦点至少 3:1。

## Typography

使用系统中文无衬线字体，不加载装饰字体。基础正文采用上方 body 规格；助手正文行高 1.7，基础控件行高 1.6。控件字体栈使用系统字体、苹方、微软雅黑和 sans-serif。

说明和辅助标签至少 1rem，区块标题 1.25rem；首次邀请标题桌面 1.75rem、手机 1.625rem。账单总额与回执重点金额使用 2rem。数字启用等宽数字属性，金额、卡号和日期更易逐项核对。

字号使用 rem，重要内容允许换行，控件随文字增长，不用固定高度裁字。可切换大字，偏好在本机保留。Lucide 图标通常为 22–24px，动作保留文字，装饰图标对读屏隐藏。

## Layout

手机以 390px 为主要设计视口，保留 320px 窄屏适配。电脑对话主列最大 720px，外层最大 800px；手机正文左右留白 16px，电脑为 24px。消息间距手机 20px、电脑 24px；卡片内边距手机 16px、电脑 20px。基础节奏沿用上方间距，不强求每个局部尺寸都落在同一步长。

页面保留一处主要滚动区，输入框常驻底部并预留安全区。多行输入随内容增长，最高 160px。只有用户处于最新位置时，新消息才自动滚动；阅读历史时保留位置。

助手正文直接显示；用户消息靠右，宽度不超过主列的 88%。每个任务只有一份可操作卡片，跟随最新相关回复；展开详情本身不移动卡片。查询其他资料后原任务仍可找回。

长资料与记录在小于 960px 时用底部抽屉，电脑用右侧栏，内容在抽屉内部滚动；打开后焦点进入当前层，关闭或按 Esc 后回到触发点。600px 以下核对字段上下排列，历史资料允许换行。

## Elevation & Depth

主工作区以平面和色调区分层次：暖白页面、白色业务表面、轻分隔线。助手正文和任务外层不再套框；业务卡片承载当前操作，内部明细以分隔线展开。抽屉遮罩使用深字色的 38% 透明度；抽屉与轻提示沿用现有组件层级，不给业务列表添加装饰阴影。

## Shapes

业务卡片圆角 16px，按钮和输入框圆角 12px，边界清晰。主按钮及输入框最小高 56px，普通触控目标通常至少 48px；这些是最小尺寸，内容增长时应增高。

按钮和输入使用清楚的焦点轮廓；基础控件为主色 3px 外轮廓、偏移 3px，旧 shell 沿用深色焦点。选中对象保留浅底、边界与可识别状态，不只改变颜色。

## Components

基础控件使用 `src/components/ui/` 内的 shadcn/ui（Radix）、Vaul、Sonner 与 Lucide React；样式为 Tailwind CSS 4 与 shell CSS，不引入全局 preflight 影响历史页面。实际实现见 [conversation.css](src/shell/conversation.css)、[journeys.css](src/shell/journeys.css) 与 [shell.css](src/shell/shell.css)。

| 组件或场景 | 共用方式 |
|---|---|
| 按钮、输入 | 主动作深橙；次动作描边或浅底；轻入口无底。字段始终有标签，错误贴近字段并关联描述 |
| 对话与工具 | 首屏需求示例和“查资料 / 办业务”进入同一对话；常驻输入支持多行和中文输入法 |
| 账户、收款人 | 搜索与大行距列表，名称/备注、银行、尾号一起显示；余额注明“查询时可用余额” |
| 转账选择 | 沿服务端当前步骤补资料，保留已知金额、付款卡和收款信息；同名候选由用户选择 |
| 账单 | 总额连同统计范围展示；月份/账户筛选，分类和单笔明细原地展开；长详情进抽屉 |
| 自动扣费 | 按有效、疑似、已退订分组；敏感核对保留一组确认和取消动作 |
| 核对与验证 | 核对清单展示对象、金额、费用、时间和实际影响；修改入口相邻。验证码等进入专用表单 |
| 配送 | 专用姓名、电话、地址表单；空值错误就地呈现。提交后按服务端掩码和引用规则展示 |
| 回执 | 对象、金额、实际结果、时间、下一步直接显示；长编号按需打开凭证抽屉 |
| 等待与恢复 | 显示真实阶段；未知进度用循环条。活跃事项“接着办”，暂停和待恢复事项先“查看进度” |
| 生活安排 | 总览、当前步骤和分项结果分开；准备查询完成不能表述为转账完成，终态隐藏取消 |
| 轻提示 | Sonner 仅用于字号、复制等普通反馈，可关闭、停留 6 秒；交易结果、错误、待办持久展示 |

未提交表单保留草稿，修改后重新核对；旧确认保持只读。自由文字交给服务端 Agent，点击沿既有任务接口，前端不自行解析真实交易意图或复制银行规则。

加载、空数据、字段错误、核对、验证、处理中、完成、失败、待核实、断线、恢复与登录过期使用同一套文字和操作关系。失败展示实际原因及可用下一步；未知结果保留核实入口。等待动画与系统减少动画设置一致，不显示假进度。

## Do's and Don'ts

- 用一句话说明当前状态，按钮直接写动作；失败和风险按实际情况说明。
- 将账户、收款人和余额展示给用户选择，保留原任务与阅读位置。
- 让重要结果留在页面上；把长编号和长资料放入抽屉。
- 保留可访问名称、键盘焦点和字段错误关系；大字时容许换行。
- 不用重复标签、额外说明或多层边框替代清楚的布局。
- 不将暂停写成可以继续，不把准备步骤完成写成银行执行成功。
- 不凭内部引用编造收件信息、卡号或银行事实，不自行增加地域电话号码规则。
- 不把原型、组件测试、真实 API、真人接受与专业安全签核合并成一个通过声明。

当前记录：121 项组件测试及真实 API、契约演示两种构建通过；独立视觉 review 为 ship。实际范围与遗留见 [03 验证记录](../.scratch/frontend-design-system/verification-03.md) 和 [独立 E2E](../.scratch/frontend-design-system/e2e-03.md)。真实转账后半程仍被后端风险核对暂停阻塞；生日核对内部引用和电话 `123` 可被接受仍属后端/契约后续项。实体手机软键盘、专业读屏、200% 浏览器缩放、人为断网与未知银行结果未包含在本轮通过声明中，用户体验接受仍待完成。
