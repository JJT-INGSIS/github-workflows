"""Validate YAML/expressions with pinned actionlint; adapt its missing $/ support."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
ACTIONLINT = 'rhysd/actionlint@sha256:b1934ee5f1c509618f2508e6eb47ee0d3520686341fec936f3b79331f9315667'


def main():
    with tempfile.TemporaryDirectory(prefix='sni25-actionlint-') as directory:
        target = Path(directory)
        workflows = target / '.github/workflows'
        workflows.mkdir(parents=True)
        for path in (ROOT / '.github/workflows').glob('*.yml'):
            # GitHub documents $/ as same-repository/same-revision. actionlint
            # 1.7.12 only understands ./; normalize this exact prefix in a copy
            # to retain all checks and local workflow input/output validation.
            text = path.read_text(encoding='utf-8').replace('uses: $/.github/workflows/', 'uses: ./.github/workflows/')
            (workflows / path.name).write_text(text, encoding='utf-8', newline='\n')
        files = [f'.github/workflows/{path.name}' for path in workflows.glob('*.yml')]
        subprocess.run(['docker', 'run', '--rm', '--mount', f'type=bind,source={target},target=/repo,readonly',
                        '-w', '/repo', ACTIONLINT, *files], check=True)


if __name__ == '__main__':
    main()
