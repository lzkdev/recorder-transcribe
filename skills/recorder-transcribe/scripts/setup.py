#!/usr/bin/env python3
"""Explicit opt-in installation; doctor alone never installs or changes login."""
import argparse
import shutil
import subprocess
import sys
import hashlib
import os
import urllib.request
from pathlib import Path

VERSION = '1.0.95'

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install-cli', action='store_true')
    parser.add_argument('--install-vad', action='store_true')
    args = parser.parse_args()
    if sys.version_info < (3, 9):
        print('Python 3.9+ required', file=sys.stderr)
        return 1
    if args.install_vad:
        from vad import MODEL, MODEL_URL, MODEL_SHA256
        python = shutil.which('python3.12') or sys.executable
        root = Path.home() / '.local/share/recorder-transcribe'
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        env = root / 'vad-env'
        if not (env / 'bin/python').exists():
            subprocess.run([python, '-m', 'venv', str(env)], check=True)
        subprocess.run([str(env / 'bin/python'), '-m', 'pip', 'install',
                        '--index-url', 'https://pypi.org/simple',
                        'onnxruntime==1.19.2', 'numpy==1.26.4'], check=True)
        with urllib.request.urlopen(MODEL_URL, timeout=60) as response:
            data = response.read(10 * 1024 * 1024)
        if hashlib.sha256(data).hexdigest() != MODEL_SHA256:
            raise ValueError('VAD model checksum mismatch')
        temp = MODEL.with_suffix('.tmp')
        temp.write_bytes(data)
        os.replace(temp, MODEL)
        return subprocess.call([str(env / 'bin/python'), str(Path(__file__).with_name('vad.py')), '--check'])
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
