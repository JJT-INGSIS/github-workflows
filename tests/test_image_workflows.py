"""Run release shell logic against a fake registry; no push or build takes place."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "sha256:" + "a" * 64
OTHER = "sha256:" + "b" * 64
FAKE_DOCKER = r"""
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
state_path = Path(os.environ['REGISTRY_STATE'])
state = json.loads(state_path.read_text())
if args[:3] == ['buildx', 'imagetools', 'inspect']:
    ref = args[3]
    digest = state.get(ref)
    if digest is None:
        sys.exit(1)
    print(json.dumps({'digest': digest}))
elif args[:3] == ['buildx', 'imagetools', 'create']:
    tag = args[args.index('--tag') + 1]
    state[tag] = os.environ.get('CREATED_DIGEST', args[-1].split('@')[1])
    state_path.write_text(json.dumps(state))
else:
    raise SystemExit('unexpected docker command')
"""


class ImageWorkflowTests(unittest.TestCase):
    def run_tag(self, source=True, existing=None, created=None):
        workflow = yaml.safe_load((ROOT / '.github/workflows/tag-service.yml').read_text())
        script = workflow['jobs']['release']['steps'][-1]['run']
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            # git rev-parse runs on a real repository but does not mutate it.
            commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
            image = 'ghcr.io/jjt-ingsis/snippets-service'
            state = {f'{image}:sha-{commit}': SOURCE} if source else {}
            if existing:
                state[f'{image}:v1.0.0'] = existing
            state_file = temp / 'registry.json'
            state_file.write_text(json.dumps(state))
            docker = temp / 'docker'
            docker.write_text(f'#!{sys.executable}\n' + FAKE_DOCKER)
            docker.chmod(0o755)
            env = {**os.environ, 'PATH': f'{directory}:{os.environ["PATH"]}',
                   'REGISTRY_STATE': str(state_file), 'REPOSITORY': 'JJT-INGSIS/snippets-service',
                   'VERSION': 'v1.0.0', 'GITHUB_STEP_SUMMARY': str(temp / 'summary')}
            if created:
                env['CREATED_DIGEST'] = created
            result = subprocess.run(['bash', '-c', script], cwd=ROOT, env=env, capture_output=True, text=True)
            return result, json.loads(state_file.read_text())

    def test_tag_aliases_same_digest_without_building(self):
        result, state = self.run_tag()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(state['ghcr.io/jjt-ingsis/snippets-service:v1.0.0'], SOURCE)

    def test_tag_without_published_commit_fails(self):
        result, state = self.run_tag(source=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(state)

    def test_version_cannot_be_moved_to_another_digest(self):
        result, state = self.run_tag(existing=OTHER)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(state['ghcr.io/jjt-ingsis/snippets-service:v1.0.0'], OTHER)

    def test_repeated_release_is_idempotent(self):
        result, _ = self.run_tag(existing=SOURCE)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_registry_copy_that_changes_digest_fails(self):
        result, _ = self.run_tag(created=OTHER)
        self.assertNotEqual(result.returncode, 0)


if __name__ == '__main__':
    unittest.main()
