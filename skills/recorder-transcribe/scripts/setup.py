#!/usr/bin/env python3
"""Explicit opt-in installation; doctor alone never installs or changes login."""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

VERSION = '1.0.95'

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install-cli', action='store_true')
    args = parser.parse_args()
    if sys.version_info < (3, 9):
        print('Python 3.9+ required', file=sys.stderr)
        return 1
    if not args.install_cli:
        return subprocess.call([sys.executable, str(Path(__file__).with_name('recorder.py')), '--doctor'])
    if not shutil.which('npm'):
        print('Install Node.js LTS from https://nodejs.org/ then rerun. npm is required.', file=sys.stderr)
        return 1
    target = Path.home() / '.local/share/recorder-transcribe/tools'
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    # No sudo, shell evaluation, global npm installation, or credential copying.
    result = subprocess.run(['npm', 'install', '--prefix', str(target), '--registry',
                             'https://registry.npmjs.org', f'@larksuite/cli@{VERSION}'])
    if result.returncode:
        return result.returncode
    cli = target / 'node_modules/.bin/lark-cli'
    print('Installed CLI:', cli)
    print('Next: run recorder.py --doctor; use the full CLI path for config/auth commands.')
    return 0

if __name__ == '__main__':
    sys.exit(main())
