"""Verify an exact prospective Git file set outside the repo, without staging or a commit."""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p3_artifacts import MANIFEST, contained

REPO = Path(__file__).resolve().parents[2]
TOOLS = ['.gitattributes', '.gitignore', 'pipeline/P3-INTEGRATION.md',
         'pipeline/requirements-p3-demo.txt', 'pipeline/start-p3-demo.ps1',
         'pipeline/tests/test_p3_handoff.py'] + ['pipeline/scripts/' + p for p in (
             'check_p3_checkout.py', 'in_memory_http.py', 'p3_artifacts.py',
             'p3_reader_check.py', 'p3_serve_demo.py', 'package_p3_handoff.py',
             'verify_p3_integration.py')]


def git_paths(root, *args):
    data = subprocess.check_output(['git', '-C', str(root), *args, '-z'])
    return set(data.decode('utf-8').rstrip('\0').split('\0')) - {''}


def planned_tree(root):
    tracked = git_paths(root, 'ls-files', '--cached')
    visible = git_paths(root, 'ls-files', '--others', '--exclude-standard')
    modified = git_paths(root, 'diff', '--name-only')
    manifest = json.loads((root / MANIFEST).read_bytes())
    data_paths = {p for group in manifest['groups'].values() for p in group['files']}
    intended = set(TOOLS) | data_paths | {MANIFEST}
    if visible != intended - tracked:
        raise ValueError(f'Tracking mismatch; missing={sorted(intended - tracked - visible)}, '
                         f'unexpected={sorted(visible - intended)}')
    if not modified.issubset(intended):
        raise ValueError(f'Unrelated tracked changes: {sorted(modified - intended)}')
    if git_paths(root, 'diff', '--cached', '--name-only'):
        raise ValueError('Expected an empty real Git index diff; nothing is staged by this script')
    for path in data_paths | {MANIFEST}:
        attr = subprocess.check_output(['git', '-C', str(root), 'check-attr', 'text', '--', path], text=True)
        if not attr.rstrip().endswith(': text: unset'):
            raise ValueError(f'Immutable artifact needs -text: {path}')
    return sorted(tracked | visible), sorted(modified | visible)


AUDIT_RUNNER = '''import sys,pathlib,runpy
original=pathlib.Path(sys.argv[1]).resolve(); output=pathlib.Path(sys.argv[2]).resolve(); script=sys.argv[3]
def deny_original(event,args):
    if event in ('open','sqlite3.connect') and args and isinstance(args[0],(str,bytes)):
        value=args[0].decode() if isinstance(args[0],bytes) else args[0]
        if value.startswith('file:'): value=value[5:].split('?')[0]
        target=pathlib.Path(value).resolve()
        if target!=output and any(target.is_relative_to(original/folder) for folder in ('data','pipeline','api')):
            raise RuntimeError('Original repository access forbidden: '+str(target))
sys.addaudithook(deny_original)
sys.argv=sys.argv[3:]
runpy.run_path(script,run_name='__main__')
'''


def verify(root, output_dir, model_root):
    if output_dir.exists():
        raise FileExistsError(output_dir)
    files, changes = planned_tree(root)
    parent = Path(tempfile.mkdtemp(prefix='smartlib-p3-clean-tree-')).resolve()
    checkout = parent / 'checkout'
    if parent.is_relative_to(root) or root.is_relative_to(parent):
        raise ValueError('Verification destination must be outside source repository')
    checkout.mkdir()
    inventory = {}
    for name in files:
        source = contained(root, name)
        target = contained(checkout, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        blob = target.read_bytes()
        if sha256(blob).digest() != sha256(source.read_bytes()).digest():
            raise ValueError(f'Copy hash mismatch: {name}')
        inventory[name] = {'bytes': len(blob), 'sha256': sha256(blob).hexdigest()}
    actual = {p.relative_to(checkout).as_posix() for p in checkout.rglob('*') if p.is_file()}
    if actual != set(files):
        raise ValueError('Prospective checkout file set differs from selected Git tree')
    output_dir.mkdir(parents=True)
    (output_dir / 'inventory.json').write_text(json.dumps(inventory, indent=2), encoding='utf-8')
    (output_dir / 'stage-paths.txt').write_text('\n'.join(changes) + '\n', encoding='utf-8')
    (output_dir / 'stage-plan.ps1').write_text(
        '# Suggested commands only; not executed.\n' +
        ''.join(f'git add -- "{p}"\n' for p in changes) +
        'git diff --cached --check\ngit diff --cached --stat\ngit diff --cached --name-only\n',
        encoding='utf-8')
    env = os.environ.copy()
    for key in ('PYTHONPATH', 'SMARTLIBAI_DEMO_SNAPSHOT', 'CLASSROOM_DEMO_SNAPSHOT'):
        env.pop(key, None)
    env.update(PYTHONDONTWRITEBYTECODE='1', SMARTLIB_TEST_NO_SOCKETS='1', OMP_NUM_THREADS='1',
               HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    results = []
    for component in ('search', 'reader', 'reader-sources', 'baseline'):
        report = output_dir / (component + '.json')
        log = output_dir / (component + '.log')
        args = [str(checkout / 'pipeline/scripts/verify_p3_integration.py'), '--root', str(checkout),
                '--component', component, '--api-smoke', '--output', str(report)]
        if component == 'search' and model_root:
            args += ['--semantic-smoke', '--model-root', str(model_root)]
        print(f'Checking {component} from {checkout}', flush=True)
        with log.open('x', encoding='utf-8') as stream:
            process = subprocess.run([sys.executable, '-I', '-B', '-c', AUDIT_RUNNER, str(root), str(report), *args],
                                     cwd=checkout, env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=300)
        results.append({'component': component, 'exit_code': process.returncode, 'report': str(report)})
        print(f'{component}: exit {process.returncode}', flush=True)
        if process.returncode:
            print(log.read_text(encoding='utf-8')[-4000:], flush=True)
    for name, expected in inventory.items():
        blob = contained(checkout, name).read_bytes()
        if len(blob) != expected['bytes'] or sha256(blob).hexdigest() != expected['sha256']:
            raise ValueError(f'Checkout mutated during verification: {name}')
    actual = {p.relative_to(checkout).as_posix() for p in checkout.rglob('*') if p.is_file()}
    if actual != set(files):
        (output_dir / 'unexpected-files.json').write_text(json.dumps({
            'extra': sorted(actual - set(files)), 'missing': sorted(set(files) - actual)}, indent=2),
            encoding='utf-8')
        raise ValueError('Tests created files inside prospective checkout')
    result = {'status': 'PASS' if all(r['exit_code'] == 0 for r in results) else 'FAIL',
              'kind': 'prospective Git filesystem; no commit or actual Git clone',
              'checkout': str(checkout), 'files': len(files), 'changed_paths': len(changes),
              'additional_bytes': sum(inventory[p]['bytes'] for p in changes),
              'exact_file_set': True, 'all_copy_hashes_valid': True,
              'immutable_data_git_text_conversion': False,
              'original_repository_reads_blocked': True, 'zip_required': False,
              'external_dependencies': ['installed Python packages', 'pinned E5 cache for query encoding'],
              'checks': results}
    (output_dir / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=REPO)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--model-root', type=Path)
    args = parser.parse_args()
    result = verify(args.root.resolve(strict=True), args.output_dir.resolve(),
                    args.model_root.resolve(strict=True) if args.model_root else None)
    raise SystemExit(0 if result['status'] == 'PASS' else 1)
