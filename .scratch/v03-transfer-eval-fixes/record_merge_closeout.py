import json
from pathlib import Path
import re
import subprocess

root = Path(__file__).resolve().parent
target = Path('C:/Users/57652/.codex/worktrees/transfer-fixes-merge-closeout/hackerthon-bank-agent')
ledger = json.loads((root / 'merge-ledger.json').read_text(encoding='utf-8'))
assert len(ledger) == 10
main = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=target, text=True).strip()
assert main == ledger[-1]['merge_commit']
comparison = json.loads((target / '.mnemon/merged-source-comparison.json').read_text(encoding='utf-8'))
assert comparison['main'] == main and not comparison['unexpected_code_differences']
report_path = sorted((target / '.mnemon/merged-main-offline-153').glob('*/report.json'))[-1]
report = json.loads(report_path.read_text(encoding='utf-8'))
assert report['revision'] == main
assert report['summary']['samples_run'] == 153
assert report['summary']['counts'] == {'Passed': 147, 'Blocked': 6}
assert len(report['platform_regressions']) == 2
assert all(r['status'] == 'Passed' for r in report['platform_regressions'])
print(json.dumps(report['summary'], ensure_ascii=True))
index = {r['pr']: r for r in ledger}
mapping = {'01':59, '02':52, '03':54, '04':58, '05':53, '06':55, '07':56, '08':57, '09':64}
rows = ['| 完整票号 | PR | 主线合并提交 |', '|---|---|---|']
for ticket, pr in mapping.items():
    row = index[pr]
    issue = next((root / 'issues').glob(ticket + '-*.md'))
    text = issue.read_text(encoding='utf-8')
    text = re.sub(r'^Status:.*$', lambda _: 'Status: resolved — 程序修复已合入并主线验证；本轮Ringo审批由用户豁免，专业评测另待\\', text, count=1, flags=re.M)
    text += f'\n\n## 2026-10-04 合入收口\n\n用户明确指示“我豁免ringo审批，合并吧”。[PR #{pr}](https://github.com/DrErwin/hackerthon-bank-agent/pull/{pr}) 已按依赖 squash 合入，主线提交 `{row["merge_commit"]}`，最终 PR 提交 `{row["rebased_head"]}` 检查通过。与已验证组合67文件一致；实际主线153离线147 Passed/6 Blocked、0 Failed/0 Error，新增评测判据15测试通过。专业安全评测、真实GLM模型问题及v0.3联合验收另待，10继续paused；不记为Ringo本人审查。上文未批准/未合入为历史。\n'
    issue.write_text(text, encoding='utf-8')
    rows.append(f'| v03-transfer-eval-fixes/{ticket} | [#{pr}](https://github.com/DrErwin/hackerthon-bank-agent/pull/{pr}) | `{row["merge_commit"]}` |')
summary = f'\n\n## 2026-10-04 本轮合入与主线复验\n\n用户明确指示“我豁免ringo审批，合并吧”；豁免仅限本轮PR51和修复01—09，不冒充Ringo已审查。10张PR均按依赖更新主线、最终提交CI通过后squash合入；原始交付头、合入前头、检查及主线提交见merge-ledger.json。\n\n' + '\n'.join(rows) + f'\n\n来源套件[PR51](https://github.com/DrErwin/hackerthon-bank-agent/pull/51) 合入 `{index[51]["merge_commit"]}`。代码主线 `{main}` 与先前组合全部67文件一致（规范换行文本比较），比较证据在 `{target}/.mnemon/merged-source-comparison.json`。主线离线153报告在 `{report_path}`：147 Passed/6 Blocked、0 Failed/0 Error；两项平台回归Passed。新增判据15项通过。Blocked为TF-VFY-16真实攻击来源缺失和TF-OBS-03—07本次未提供真实React构建。完整红线Unverified，版本NotAccepted。\n\n01—09按程序范围标为resolved；票10paused不变。原评测实施票03仅工程套件已合并，实际GLM问题及全绿条件尚未补齐，保持in_progress；04和原12继续blocked。没有运行GLM、联系队员、同步飞书、合并他人PR60—63或开启下一阶段。\n'
summary += '\n代码主线[Repository checks](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/37190825047)通过：完整后端327项、MockBank14项；新增判据本机15项通过。327为CI整个backend收集范围，先前组合326仅backend/app，数字不相加。\n'
execution = root / 'execution.md'
text = execution.read_text(encoding='utf-8')
text = re.sub(r'^Status:.*$', 'Status: merged-and-program-verified — PR51及修复01—09已合入；10暂停，专业安全评测和v0.3验收另待。', text, count=1, flags=re.M)
execution.write_text(text + summary, encoding='utf-8')
for name in ['spec.md', 'ticket-proposal.md']:
    path = root / name
    text = path.read_text(encoding='utf-8')
    if name == 'ticket-proposal.md':
        text = re.sub(r'^Status:.*$', lambda _: 'Status: resolved — 本轮01—09程序范围已合入并验证；10保持paused，版本验收另待\\', text, count=1, flags=re.M)
    text += '\n\n## 2026-10-04 最新合入状态\n\n用户本轮明确豁免Ringo审批并授权合并；PR51及修复01—09已合入，程序主线复验完成。审批豁免不是Ringo已审查；10继续暂停，专业安全评测与v0.3验收未提升。上文未授权/待合入为历史；最新逐票提交及验证见[执行记录](execution.md)。\n'
    path.write_text(text, encoding='utf-8')
source_ticket = root.parent / 'v03-transfer-evals/issues/03-eval-automation-suite.md'
text = source_ticket.read_text(encoding='utf-8')
text += f'\n\n## 2026-10-04 本轮合入补充\n\n用户已豁免本轮Ringo审批并授权合并，[PR51](https://github.com/DrErwin/hackerthon-bank-agent/pull/51) 已合入 `{index[51]["merge_commit"]}`；后续程序修复与口径修正01—09也已合入。主线 `{main}` 离线153样本147 Passed/6 Blocked、0 Failed/0 Error。此票工程套件已合并，真实GLM仍有历史未解决结果，原全绿验收条件未全满足，维持in_progress；04及原12仍blocked。不将本轮审批豁免记为Ringo本人审查。\n'
source_ticket.write_text(text, encoding='utf-8')
(root / 'closeout-table.md').write_text('\n'.join(rows) + '\n', encoding='utf-8')
