"""Optional archive exporter; Git checkout is the supported P3 distribution path."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile, ZIP_DEFLATED

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p3_artifacts import MANIFEST, GROUPS, check_files, contained

REPO = Path(__file__).resolve().parents[2]


def build(root, component, output):
    root = root.resolve(strict=True)
    manifest = json.loads((root / MANIFEST).read_bytes())
    data = dict(manifest['groups'][GROUPS[component]]['files'])
    if component == 'reader':
        data.update(manifest['groups'][GROUPS['reader-sources']]['files'])
    check_files(root, data)
    tracked = subprocess.check_output(['git', '-C', str(root), 'ls-files'], text=True).splitlines()
    code = [p for p in tracked if
            (p.startswith(('api/src/', 'pipeline/ai_library/')) and p.endswith('.py'))
            or p in ('api/tests/catalog_fixture.py', 'pipeline/README.md', 'LICENSE', 'LICENSE.md')
            or (p.startswith(('api/', 'pipeline/')) and '/requirements' in p and p.endswith('.txt'))]
    tools = ['pipeline/scripts/' + p for p in (
        'verify_p3_integration.py', 'p3_reader_check.py', 'p3_artifacts.py', 'in_memory_http.py',
        'p3_serve_demo.py')]
    tools += ['pipeline/P3-INTEGRATION.md', 'pipeline/start-p3-demo.ps1',
              'pipeline/requirements-p3-demo.txt', MANIFEST]
    paths = sorted(set(data) | set(code) | set(tools))
    payload = {p: contained(root, p).read_bytes() for p in paths}
    envelope = {'schema_version': 1, 'component': component, 'snapshot_id': 'smartlibai-demo-v4',
                'scope': 'classroom_demo' if component == 'search' else 'group_handoff_staging_only',
                'external_dependencies': ['Python packages from requirements',
                    'Pinned E5 model cache only for semantic queries; never book data/vectors'],
                'files': {p: {'bytes': len(blob), 'sha256': sha256(blob).hexdigest()}
                          for p, blob in payload.items()}}
    payload['handoff_manifest.json'] = (json.dumps(envelope, ensure_ascii=False, indent=2) + '\n').encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, 'x', compression=ZIP_DEFLATED) as archive:
        for name, blob in payload.items():
            archive.writestr(name, blob)
    blob = output.read_bytes()
    return {'component': component, 'path': str(output.resolve()), 'files': len(payload),
            'uncompressed_bytes': sum(map(len, payload.values())), 'bytes': len(blob),
            'sha256': sha256(blob).hexdigest(), 'required_data_files': len(data)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=REPO)
    parser.add_argument('--component', choices=['search', 'reader'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.root, args.component, args.output), ensure_ascii=False))
