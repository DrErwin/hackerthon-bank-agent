import hashlib
import json
from pathlib import Path
import subprocess

target = Path('C:/Users/57652/.codex/worktrees/transfer-fixes-merge-closeout/hackerthon-bank-agent')
combo = Path('C:/Users/57652/.codex/worktrees/transfer-fixes-final-validation/hackerthon-bank-agent')
manifest = json.loads((combo / '.mnemon/assembly-manifest.json').read_text(encoding='utf-8'))
results = []
for raw in manifest['file_sha256']:
    relative = raw.replace('\\', '/')
    before = (combo / relative).read_text(encoding='utf-8')
    after = (target / relative).read_text(encoding='utf-8')
    results.append({'file': relative, 'same_text': before == after, 'merged_sha256': hashlib.sha256(after.encode()).hexdigest()})
unexpected = [r for r in results if not r['same_text'] and not r['file'].endswith('.md')]
record = {'main': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=target, text=True).strip(),
          'comparison': 'UTF-8 text with normalized line endings', 'files': results, 'unexpected_code_differences': unexpected}
(target / '.mnemon').mkdir(exist_ok=True)
(target / '.mnemon/merged-source-comparison.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'main': record['main'], 'files_checked': len(results), 'documentation_differences': [r['file'] for r in results if not r['same_text'] and r['file'].endswith('.md')], 'unexpected_code_differences': unexpected}))
raise SystemExit(1 if unexpected else 0)
