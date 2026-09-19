const fs = require('node:fs');
const path = require('node:path');
const root = __dirname;
const node = (id,type,label,sublabel,x,y,w=130,h=68)=>({id,type,label,sublabel,pos:[x,y],size:[w,h]});
const edge = (id,from,to,label,extra={})=>({id,from,to,label,...extra});
const down={fromSide:'bottom',toSide:'top'};
const up={fromSide:'top',toSide:'bottom'};
const common={locale:'zh-CN',quality_profile:'showcase'};
const agent={schema_version:1,diagram_type:'architecture',meta:{...common,title:'Agent 内部架构 · v0.4 设计评审',viewBox:[1080,660]},components:[
node('trusted-task','external','可信任务入口','来自 API · 身份与任务编号',25,265),
node('main-harness','backend','主 Agent / Harness','Deep Agents · 对话与选能力',200,265),
node('graph-engine','backend','流程运行引擎','LangGraph · 分支 / 暂停',375,265),
node('capability-contract','security','能力目录与适配','模块准入 / 可信上下文',550,265),
node('capability-module','backend','业务模块','函数 或 LangGraph 子流程',725,265),
node('guarded-tools','security','统一工具执行器','鉴权与确认 → 私有工具',900,265),
node('context-memory','database','上下文与受控记忆','压缩 / 用户隔离 / 受控写入',200,70),
node('model-adapter','backend','统一模型入口','配置 / 超时 / 供应商适配',375,70),
node('resume-control','backend','中断恢复协调','先核对，再续办原任务',375,485),
node('graph-checkpoints','database','运行检查点','保存执行位置与任务状态',550,485),
node('operation-ledger','database','工具操作记录','稳定操作编号 / 实际结果',725,485),
node('audit-events','security','审计事件与证据','调用链 / 判定 / 缺口标注',900,485)
],connections:[
edge('accept-task','trusted-task','main-harness','任务请求',{variant:'emphasis'}),
edge('run-on-graph','main-harness','graph-engine','运行承载',{variant:'emphasis'}),
edge('dispatch-capability','graph-engine','capability-contract','推进调用',{variant:'emphasis'}),
edge('invoke-module','capability-contract','capability-module','统一契约',{variant:'security'}),
edge('guard-private-tools','capability-module','guarded-tools','工具调用',{variant:'security'}),
edge('manage-context','main-harness','context-memory','受控读写',{...up,labelAt:[265,180]}),
edge('call-model','main-harness','model-adapter','模型调用',{fromSide:'top',toSide:'left'}),
edge('persist-state','graph-engine','graph-checkpoints','状态落盘',{...down}),
edge('resume-task','resume-control','graph-engine','继续原任务',up),
edge('read-checkpoint','resume-control','graph-checkpoints','读取位置'),
edge('record-operation','guarded-tools','operation-ledger','记录操作',{fromSide:'bottom',toSide:'top'}),
edge('record-audit','guarded-tools','audit-events','记录证据',{...down,labelAt:[965,455]})
],cards:[
{dot:'cyan',title:'内部职责 · 尚未实现验证',items:['Harness 选能力；LangGraph 承载主流程与业务子流程。','API、业务服务和外部供应商的位置见系统总览。']},
{dot:'rose',title:'唯一受控工具入口',items:['模块准入不替代逐次鉴权；私有工具获准后调用应用服务。','模块不得直连供应商；局部 Agent 仅保留扩展位置。']},
{dot:'amber',title:'恢复与审计分开',items:['恢复同时核对检查点、操作记录及当前授权；未知则停。','Harness、运行引擎、工具与恢复均上报审计；审计只读。']}
]};
// The complete system module map is authored separately in build-system-modules.cjs.
fs.writeFileSync(path.join(root,'agent-internal-architecture.json'),JSON.stringify(agent,null,2)+'\n');

