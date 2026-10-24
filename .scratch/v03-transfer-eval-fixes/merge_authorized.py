import json
import os
from pathlib import Path
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent
WT = Path('C:/Users/57652/.codex/worktrees')
PLAN = [
    (52, 'transfer-fix-02', None, 54),
    (53, 'transfer-fix-05', None, 55),
    (56, 'transfer-fix-07', None, None),
    (64, 'transfer-fix-09', None, None),
    (55, 'transfer-fix-06', 'e23df725a0897cae2728cb8190b480c7156f5f53', None),
    (54, 'transfer-fix-03', '461d539db6abb4ff1fd2c714ac8c6a3504317a18', 58),
    (58, 'transfer-fix-04', '6d53860f8fadf47f0877a4faa4ceba194e54a72d', None),
    (57, 'transfer-fix-08', None, None),
    (51, 'transfer-eval-suite', None, 59),
    (59, 'transfer-fix-01', '58740f541a6777f87490593a91515e4a2efda28a', None),
]
LEDGER = ROOT / 'merge-ledger.json'
records = json.loads(LEDGER.read_text(encoding='utf-8')) if LEDGER.exists() else []
env = dict(os.environ, GIT_EDITOR='true', PYTHONIOENCODING='utf-8')

def run(args, cwd, quiet=False):
    p = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if not quiet and (p.stdout.strip() or p.stderr.strip()):
        print(p.stdout.strip(), p.stderr.strip(), flush=True)
    if p.returncode:
        raise RuntimeError(f'{args}: {p.stdout} {p.stderr}')
    return p.stdout.strip()

def view(number, cwd):
    return json.loads(run(['gh', 'pr', 'view', str(number), '--json', 'state,headRefOid,headRefName,baseRefName,isDraft,body,statusCheckRollup,mergeCommit'], cwd, True))

for number, name, oldbase, child in PLAN:
    cwd = WT / name / 'hackerthon-bank-agent'
    pr = view(number, cwd)
    if pr['state'] == 'MERGED':
        print(f'PR {number} already merged: {pr["mergeCommit"]}', flush=True)
        continue
    print(f'PREPARE PR {number}', flush=True)
    if run(['git', 'status', '--porcelain', '--untracked-files=no'], cwd, True):
        raise RuntimeError(f'Dirty source worktree PR {number}')
    run(['git', 'fetch', 'origin'], cwd)
    original = run(['git', 'rev-parse', 'HEAD'], cwd, True)
    base = run(['git', 'rev-parse', 'origin/main'], cwd, True)
    if original != pr['headRefOid']:
        raise RuntimeError(f'Unexpected head PR {number}')
    backup = f'codex/merge-source-{number}-{original[:7]}'
    if subprocess.run(['git', 'show-ref', '--verify', '--quiet', f'refs/heads/{backup}'], cwd=cwd).returncode:
        run(['git', 'branch', backup, original], cwd)
    already_current = subprocess.run(['git', 'merge-base', '--is-ancestor', 'origin/main', 'HEAD'], cwd=cwd).returncode == 0
    run(['git', 'rebase', '--onto', 'origin/main', oldbase] if oldbase and not already_current else ['git', 'rebase', 'origin/main'], cwd)
    head = run(['git', 'rev-parse', 'HEAD'], cwd, True)
    run(['git', 'diff', '--check', 'origin/main...HEAD'], cwd)
    run(['git', 'push', f'--force-with-lease=refs/heads/{pr["headRefName"]}:{original}', 'origin', f'HEAD:refs/heads/{pr["headRefName"]}'], cwd)
    if pr['baseRefName'] != 'main':
        run(['gh', 'pr', 'edit', str(number), '--base', 'main'], cwd)
    if pr['isDraft']:
        run(['gh', 'pr', 'ready', str(number)], cwd)
    body = pr['body']
    marker = '### 本轮合并授权（2026-10-04）'
    if marker not in body:
        body += '\n\n' + marker + '\n\n用户明确指示：“我豁免ringo审批，合并吧”。本 PR 属于本轮转账评测及 01—09 程序修复范围；记录为项目负责人豁免本轮 Ringo 真人审批，不记作 Ringo 已审查，不替代安全专业评测或 v0.3 最终验收。票 10 继续暂停。合并前更新到最新 main 并核验当前提交 CI。\n'
        bodyfile = ROOT / f'pr-{number}-merge-body.md'
        bodyfile.write_text(body.replace('`n', '\n'), encoding='utf-8')
        run(['gh', 'pr', 'edit', str(number), '--body-file', str(bodyfile)], cwd)
    deadline = time.monotonic() + 900
    previous = None
    while True:
        latest = view(number, cwd)
        if latest['headRefOid'] != head:
            raise RuntimeError(f'PR {number} head changed externally')
        checks = latest['statusCheckRollup']
        status = [(c.get('name', c.get('context')), c.get('status'), c.get('conclusion', c.get('state'))) for c in checks]
        if status != previous:
            print(f'PR {number} CI {head[:7]}: {status}', flush=True)
            previous = status
        if checks and all(c.get('conclusion') in ('SUCCESS', 'SKIPPED', 'NEUTRAL') or c.get('state') == 'SUCCESS' for c in checks):
            break
        if any(c.get('conclusion') in ('FAILURE', 'CANCELLED', 'TIMED_OUT', 'ACTION_REQUIRED') or c.get('state') in ('FAILURE', 'ERROR') for c in checks):
            raise RuntimeError(f'PR {number} CI failed')
        if time.monotonic() > deadline:
            raise RuntimeError(f'PR {number} CI timeout')
        time.sleep(15)
    run(['git', 'fetch', 'origin'], cwd)
    if run(['git', 'rev-parse', 'origin/main'], cwd, True) != base:
        raise RuntimeError(f'Main changed externally before PR {number} merge')
    if child:
        run(['gh', 'pr', 'edit', str(child), '--base', 'main'], cwd)
    run(['gh', 'pr', 'merge', str(number), '--squash', '--match-head-commit', head], cwd)
    merged = view(number, cwd)
    if merged['state'] != 'MERGED':
        raise RuntimeError(f'PR {number} merge not confirmed')
    records.append({'pr': number, 'source_head': original, 'rebased_head': head, 'base': base, 'merge_commit': merged['mergeCommit']['oid'], 'checks': checks, 'approval': 'user-exempted-ringo-20261004'})
    LEDGER.write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'MERGED PR {number}: {merged["mergeCommit"]["oid"]}', flush=True)
