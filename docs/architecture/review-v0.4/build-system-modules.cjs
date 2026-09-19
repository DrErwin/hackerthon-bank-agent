const fs=require('node:fs');
const path=require('node:path');
const n=(id,type,label,sublabel,x,y)=>({id,type,label,sublabel,pos:[x,y],size:[180,78]});
const e=(id,from,to,label,extra={})=>({id,from,to,label,...extra});
const spec={schema_version:1,diagram_type:'architecture',meta:{title:'系统架构 · 五大子系统',locale:'zh-CN',quality_profile:'showcase',viewBox:[1160,650]},components:[
n('user-interface','frontend','前端用户交互','对话、进度、确认与结果',35,210),
n('inner-harness','backend','内层 Harness','Deep Agents · 组织任务与工具',335,210),
n('security-foundation','security','安全基座','统一授权、校验与敏感确认',635,210),
n('mock-bank','backend','模拟银行','执行模拟业务，返回实际结果',935,210),
n('langgraph-framework','backend','LangGraph 框架','承载运行状态、分支、暂停与恢复',335,445)
],boundaries:[{kind:'region',label:'Agent 运行底座 · Harness 基于 LangGraph 构建',wraps:['inner-harness','langgraph-framework'],pad:24}],connections:[
e('user-request','user-interface','inner-harness','请求 / 确认',{variant:'emphasis',fromSide:'right',toSide:'left'}),
e('visible-response','inner-harness','user-interface','进度 / 结果',{fromSide:'left',toSide:'right',labelAt:[275,278]}),
e('tool-request','inner-harness','security-foundation','提交工具调用',{variant:'security'}),
e('authorized-action','security-foundation','mock-bank','校验通过才执行',{variant:'security'}),
e('graph-runtime','inner-harness','langgraph-framework','依托运行引擎',{fromSide:'bottom',toSide:'top',labelAt:[425,302]})
],cards:[
{dot:'cyan',title:'Harness 与 LangGraph 的关系',items:['Harness 组织任务和工具调用；LangGraph 提供底层运行能力。','二者是构建与承载关系，不是两个独立 Agent 或两级审批。']},
{dot:'rose',title:'银行操作必须经过安全基座',items:['安全基座获准后调用模拟银行；银行入口再次校验关键条件。','银行实际结果沿调用链返回；安全拒绝或需确认时不执行。']},
{dot:'amber',title:'用户确认与系统边界',items:['前端经 API 提交请求，以 SSE 接收进度；确认后续办原任务。','v0.4 设计稿，尚未实现验证；当前自建模拟银行，不接真实银行。']}
]};
fs.writeFileSync(path.join(__dirname,'system-overview.json'),JSON.stringify(spec,null,2)+'\n');

