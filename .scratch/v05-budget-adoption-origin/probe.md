# 隔离来源探针

Date: 2026-10-25；代码基线 `430236645887f3e77d4d211e6dd2c90558479425`。

从本独立 worktree 的 backend 目录，将以下 Python 片段送入 `python -`。只调用现有测试工厂和现有 API/Harness；TemporaryDirectory 自动清理，未新增或修改运行代码文件。不是业务预算采用测试，不运行 CI 或全量测试。

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
import json
from fastapi.testclient import TestClient
from app.api.test_app import make_app, enter, post, bank_counts
from app.api.test_parent_child_api import register_scripted, cross_waiting_input, succeeded, RESUMED
from app.agent_platform.model import ContinueProposal
from app.contracts.common import OperationLevel
from app.contracts.platform import TrustedContext
from app.storage import ApplicationStore

outcomes=[]
for mode in ('f10', 'model_continuation'):
    with TemporaryDirectory(prefix='budget-origin-probe-') as directory:
        path=Path(directory)
        script=[succeeded()]
        def prepare(runtime):
            register_scripted(runtime,'cross','cross.test_parent',script,level=OperationLevel.READ,side_effect=False)
        app=make_app(path,prepare=prepare)
        with TestClient(app) as client:
            session=enter(client)
            thread=post(client,'/threads').json()['data']['thread_id']
            api=app.state.api
            snapshot={'capability_name':'cross.test_parent','trace_id':str(uuid4()),'request_id':str(uuid4()),'intent_text':'budget origin probe','config_version':'test-v1','result':cross_waiting_input().model_dump(mode='json')}
            api.runtime.application.create_task('XPARENT','U1',session['session_id'],'D1','R1','waiting_input',snapshot)
            task=api.runtime.application.update_task('U1','D1','XPARENT',0,'R1','waiting_input',None,snapshot)
            api.store.write('INSERT INTO api_tasks (task_id,thread_id,user_id,session_id,demo_round_id,run_id,created_at,request_id,intent_text) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',('XPARENT',thread,'U1',session['session_id'],'D1','R1','2026-10-25T10:00:00+08:00',str(uuid4()),'budget origin probe'))
            context=TrustedContext(user_id='U1',session_id=session['session_id'],task_id='XPARENT',run_id='R1',demo_round_id='D1',parent_task_id=None)
            prompt=api.runtime.harness._session_context_summary(context)
            before=bank_counts(path)
            RESUMED.clear()
            request_id=str(uuid4())
            forged_status=None
            if mode=='f10':
                forged=post(client,'/tasks/XPARENT/inputs',interaction_id='CX1',selected_option_id='OPT_APPLY',source='human')
                forged_status=forged.status_code
                assert forged_status in (400,422)
                response=post(client,'/tasks/XPARENT/inputs',request_id=request_id,interaction_id='CX1',selected_option_id='OPT_APPLY')
            else:
                api.runtime.harness.planner.proposal=ContinueProposal(task_id='XPARENT',task_revision=task.revision,action='provide_input',selected_option_id='OPT_APPLY')
                response=post(client,f'/threads/{thread}/messages',request_id=request_id,text='继续')
            current=ApplicationStore(path/'application.sqlite').get_task('U1','D1','XPARENT')
            assert RESUMED==[{'choice':'OPT_APPLY'}], (response.status_code, RESUMED)
            assert before==bank_counts(path)==(0,0)
            outcomes.append({'path':mode,'http_status':response.status_code,'forged_source_http_status':forged_status,'module_response':list(RESUMED),'reopened_task_status':current.status.value,'snapshot_keys':sorted(current.snapshot),'option_visible_to_planner':'OPT_APPLY' in (prompt or ''),'receipt_endpoints':[r['endpoint'].split('/')[1] for r in api.store.rows('SELECT endpoint FROM api_requests WHERE request_id=?',(request_id,))],'bank_operation_and_ledger_counts':before})
print(json.dumps(outcomes,ensure_ascii=False,indent=2))
```

实际输出关键项：F10 HTTP 200，伪造 source body HTTP 400；model_continuation HTTP 202；两者 module_response 均为 `[{"choice":"OPT_APPLY"}]`、重开任务均 succeeded、option_visible_to_planner 均 true、银行操作与流水计数均 [0,0]。snapshot_keys 均为 capability_name / completed_bill_scope / config_version / intent_text / request_id / result / trace_id，没有本次输入的来源记录。后者的请求回执另有 message-continuation，未进入 module response。

首次探针对额外字段预期 422，但 API 将校验失败映射为 400，故中止；修正后完整探针退出码0。没有把首次中止算作通过，没有因此修改服务代码。
