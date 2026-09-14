#!/usr/bin/env python3
"""Local audio -> authenticated lark-cli -> Feishu Minutes. Python 3.9+."""
import argparse
import contextlib
import fcntl
import hashlib
import json
import math
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

EXTENSIONS = {'.wav', '.mp3', '.opus', '.ogg', '.m4a', '.aac', '.flac', '.wma', '.amr'}

class WorkflowError(Exception):
    pass


def run(argv, timeout=60, cwd=None):
    try:
        p = subprocess.run([str(x) for x in argv], capture_output=True, text=True,
                           timeout=timeout, cwd=cwd)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise WorkflowError(f'{Path(argv[0]).name}: command unavailable or timed out') from e
    if p.returncode:
        # Provider stderr may contain credentials/URLs. Do not echo it automatically.
        raise WorkflowError(f'{Path(argv[0]).name}: exit {p.returncode}; inspect auth/scopes/quota with the CLI')
    return p.stdout


def probe(file):
    raw = run(['ffprobe', '-v', 'error', '-show_entries',
               'format=duration:stream=codec_type,duration', '-of', 'json', file])
    try:
        data = json.loads(raw)
        if not any(s.get('codec_type') == 'audio' for s in data.get('streams', [])):
            raise ValueError('no audio')
        duration = float(data['format']['duration'])
        if not math.isfinite(duration) or not 1 <= duration <= 21600:
            raise ValueError('duration outside 1 second to 6 hours')
        return duration
    except (ValueError, KeyError, TypeError) as e:
        raise WorkflowError('Audio must have a finite duration between 1 second and 6 hours') from e


def resolve_audio(file):
    source = Path(file).expanduser().resolve(strict=True)
    if not source.is_file() or source.stat().st_size == 0:
        raise WorkflowError('Empty or non-regular audio file')
    if source.suffix.lower() not in EXTENSIONS:
        raise WorkflowError('Unsupported audio extension')
    try:
        return source, probe(source)
    except WorkflowError:
        if source.suffix.lower() != '.opus':
            raise
        # Headerless/vendor Opus is never uploaded on a size-only heuristic.
        twins = [p for p in source.parent.iterdir()
                 if p.stem == source.stem and p.suffix.lower() == '.wav' and p.is_file()]
        if len(twins) != 1:
            raise WorkflowError('Undecodable Opus requires one valid same-stem WAV')
        return twins[0].resolve(), probe(twins[0])


def sha256(file):
    h = hashlib.sha256()
    with open(file, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def atomic_json(file, data):
    file = Path(file)
    fd, name = tempfile.mkstemp(dir=file.parent, prefix='.state-')
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, file)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@contextlib.contextmanager
def locked(directory):
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(directory / '.lock', 'a') as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as e:
            raise WorkflowError('Another workflow is running in this state directory') from e
        yield


class Lark:
    def __init__(self, executable='lark-cli'):
        self.executable = executable

    def call(self, args, cwd, timeout=360):
        raw = run([self.executable, *args, '--as', 'user', '--format', 'json'], timeout, cwd)
        try:
            obj = json.loads(raw)
            if not isinstance(obj, dict) or obj.get('error') or obj.get('ok') is False or obj.get('code', 0) not in (0, None):
                raise ValueError('provider error')
            result = obj.get('data', obj)
            if not isinstance(result, dict):
                raise ValueError('invalid data')
            return result
        except (ValueError, TypeError) as e:
            raise WorkflowError('Unrecognized or failed lark-cli JSON response; state retained') from e


def transcript_has_content(text):
    # CLI exports a metadata header even when the upstream transcript is empty.
    lines = text.splitlines()
    if lines and re.match(r'^\d{4}-\d{2}-\d{2}.*\|', lines[0]):
        lines = lines[1:]
        while lines and not lines[0].strip(): lines.pop(0)
        if lines and lines[0].strip().startswith(('Keywords:', '关键词:','关键词：')):
            lines = lines[1:]
    return any(line.strip() for line in lines)


def speech_screen(source):
    python = Path.home() / '.local/share/recorder-transcribe/vad-env/bin/python'
    if not python.exists():
        raise WorkflowError('Speech screening unavailable: run python3 scripts/setup.py --install-vad')
    raw = run([python, Path(__file__).with_name('vad.py'), source], timeout=600)
    try:
        data = json.loads(raw)
        if not all(math.isfinite(float(data[k])) for k in ('speech_seconds','speech_ratio','analyzed_seconds')):
            raise ValueError('invalid VAD result')
        if not 0 <= data['speech_ratio'] <= 1 or data['analyzed_seconds'] <= 0:
            raise ValueError('invalid VAD result')
        data['needs_confirm'] = data['speech_seconds'] < 1 or data['speech_ratio'] < 0.01
        return data
    except (ValueError, KeyError, TypeError) as e:
        raise WorkflowError('Speech screening failed; no upload performed') from e


def fetch_detail(state, job_dir, provider):
    # A read retry cannot create a new minute.
    data = provider.call(['minutes', '+detail', '--minute-tokens', state['minute_token'],
                          '--wait-ready', '--wait-timeout-seconds', '300',
                          '--transcript', '--summary', '--todo', '--chapter', '--keyword',
                          '--output-dir', str(job_dir), '--overwrite'], job_dir)
    atomic_json(job_dir / 'detail.json', data)
    rows = data.get('minutes', [])
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise WorkflowError('Missing minute detail; do not mark complete')
    row = rows[0]
    if row.get('minute_token') != state['minute_token']:
        raise WorkflowError('Minute token mismatch')
    artifacts = row.get('artifacts') or {}
    transcript = artifacts.get('transcript_file') if isinstance(artifacts, dict) else None
    if row.get('error') or row.get('status') not in (None, '', 'OK'):
        state['status'] = 'pending'
        return state
    if not transcript:
        state.update(status='empty_result', summary_available=bool(artifacts.get('summary')))
        return state
    file = Path(transcript)
    if not file.is_absolute():
        file = job_dir / file
    file = file.resolve()
    if job_dir.resolve() not in file.parents or not file.is_file():
        raise WorkflowError('Transcript is missing or outside the output directory')
    # Empty transcripts are valid for silence; never invent speech or a summary.
    state.update(status='done' if transcript_has_content(file.read_text()) else 'empty_result', transcript_file=str(file),
                 summary_available=bool(artifacts.get('summary')))
    return state


def process(file, state_dir, provider=None, check_only=False, name=None, allow_low_speech=False):
    source, duration = resolve_audio(file)
    fingerprint = sha256(source)
    result = {'source': str(source), 'sha256': fingerprint, 'duration_seconds': duration}
    screening = speech_screen(source)
    result['speech_screen'] = screening
    if screening['needs_confirm'] and not allow_low_speech:
        return dict(result, status='needs_confirm', reason='Little or no speech detected; review before uploading')
    if check_only:
        return dict(result, status='valid')
    provider = provider or Lark()
    with locked(state_dir):
        job_dir = state_dir / fingerprint
        job_dir.mkdir(exist_ok=True, mode=0o700)
        state_file = job_dir / 'state.json'
        # Corrupt state must not silently reset deduplication.
        state = json.loads(state_file.read_text()) if state_file.exists() else dict(result, status='new')
        if state['status'] in ('done', 'empty_result'):
            transcript = Path(state.get('transcript_file', ''))
            if not transcript.is_file() or not transcript_has_content(transcript.read_text()):
                state['status'] = 'empty_result'
                atomic_json(state_file, state)
                return state
            return dict(state, status='cached')
        if state['status'] in ('uploading', 'creating'):
            raise WorkflowError(f'Uncertain {state["status"]} outcome; reconcile remote resources before retry: {state_file}')
        try:
            if not state.get('file_token'):
                with tempfile.TemporaryDirectory(prefix='recorder-', dir=job_dir) as temp:
                    temp = Path(temp)
                    copied = temp / ('source' + source.suffix.lower())
                    shutil.copyfile(source, copied)
                    if sha256(copied) != fingerprint:
                        raise WorkflowError('Source changed during copy; no upload performed')
                    upload = copied
                    if copied.suffix in ('.opus', '.ogg', '.flac') or copied.stat().st_size > 18 * 1024 * 1024:
                        upload = temp / 'upload.mp3'
                        run(['ffmpeg', '-nostdin', '-v', 'error', '-xerror', '-i', copied,
                             '-map', '0:a:0', '-vn', '-ac', '1', '-ar', '16000', '-b:a', '64k', upload], 300)
                        if abs(probe(upload) - duration) > 1:
                            raise WorkflowError('Transcoded duration mismatch')
                    if upload.stat().st_size > 6 * 1024 ** 3:
                        raise WorkflowError('Upload exceeds 6 GiB')
                    state['status'] = 'uploading'
                    atomic_json(state_file, state)
                    uploaded = provider.call(['drive', '+upload', '--file', str(upload),
                                               '--name', (name or source.stem) + upload.suffix], temp)
                    if not isinstance(uploaded.get('file_token'), str) or not uploaded['file_token']:
                        raise WorkflowError('Upload response missing file_token')
                    state.update(status='uploaded', file_token=uploaded['file_token'])
                    atomic_json(state_file, state)
            if not state.get('minute_token'):
                state['status'] = 'creating'
                atomic_json(state_file, state)
                created = provider.call(['minutes', '+upload', '--file-token', state['file_token']], job_dir)
                if not isinstance(created.get('minute_token'), str) or not created['minute_token']:
                    raise WorkflowError('Creation response missing minute_token')
                state.update(status='pending', minute_token=created['minute_token'],
                             minute_url=created.get('minute_url'))
                atomic_json(state_file, state)
            state = fetch_detail(state, job_dir, provider)
            state.pop('last_error', None)
            atomic_json(state_file, state)
            return state
        except WorkflowError as e:
            state['last_error'] = str(e)
            atomic_json(state_file, state)
            raise


REQUIRED_SCOPES = {'drive:file:upload', 'drive:drive.metadata:readonly',
                   'minutes:minutes.upload:write', 'minutes:minutes.basic:read',
                   'minutes:minutes.artifacts:read'}
TOOLS_DIR = Path.home() / '.local/share/recorder-transcribe/tools'


def find_cli():
    return os.environ.get('LARK_CLI') or shutil.which('lark-cli') or str(TOOLS_DIR / 'node_modules/.bin/lark-cli')


def doctor(executable):
    checks = {'python': sys.version_info >= (3, 9),
              'ffmpeg': bool(shutil.which('ffmpeg')), 'ffprobe': bool(shutil.which('ffprobe')),
              'lark_cli': bool(shutil.which(executable))}
    actions = []
    if not checks['ffmpeg'] or not checks['ffprobe']:
        actions.append('Install ffmpeg including ffprobe: macOS: brew install ffmpeg; Ubuntu/Debian: sudo apt install ffmpeg')
    if not checks['lark_cli']:
        actions.append('Install official pinned CLI: python3 scripts/setup.py --install-cli (run from skill folder)')
        return {'ready': False, 'checks': checks, 'next_steps': actions}
    vad_python = Path.home() / '.local/share/recorder-transcribe/vad-env/bin/python'
    try:
        checks['speech_vad'] = json.loads(run([vad_python, Path(__file__).with_name('vad.py'), '--check']))['ready'] is True
    except (WorkflowError, ValueError, KeyError, TypeError):
        checks['speech_vad'] = False
        actions.append('Install local speech screening: python3 scripts/setup.py --install-vad')
    try:
        for cmd, flags in [('drive', ['--file', '--name']), ('minutes', ['--file-token'])]:
            text = run([executable, cmd, '+upload', '--help'])
            checks[cmd + '_upload'] = all(f in text for f in flags)
        text = run([executable, 'minutes', '+detail', '--help'])
        checks['minutes_detail'] = all(f in text for f in ('--minute-tokens', '--transcript', '--output-dir'))
        auth = json.loads(run([executable, 'auth', 'status', '--json']))
        checks['configured'] = bool(auth.get('appId'))
        user = auth.get('identities', {}).get('user', {})
        checks['user_login'] = user.get('available') is True and user.get('status') == 'ready'
        granted = user.get('scope', '')
        granted = set(granted.replace(',', ' ').split()) if isinstance(granted, str) else set(granted or [])
        missing = sorted(REQUIRED_SCOPES - granted)
        checks['scopes'] = not missing
        if not checks['configured']:
            actions.append('Configure an app: lark-cli config init; complete setup yourself; never paste secrets into chat')
        if not checks['user_login'] or missing:
            actions.append('Authorize your user account: lark-cli auth login --scope "' + ' '.join(sorted(REQUIRED_SCOPES | {'offline_access'})) + '"')
        if not all(checks.get(k, False) for k in ('drive_upload', 'minutes_upload', 'minutes_detail')):
            actions.append('CLI incompatible: install the documented version or inspect command help; do not upload')
    except (WorkflowError, ValueError, TypeError, AttributeError) as e:
        checks['cli_inspection'] = False
        actions.append('CLI/auth inspection failed; run lark-cli auth status and lark-cli config init if unconfigured')
    return {'ready': all(checks.values()), 'checks': checks, 'next_steps': actions,
            'note': 'Local readiness only. Server permissions, quota, network and transcript quality require a real authorized sample.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', nargs='?')
    parser.add_argument('--batch', action='store_true', help='Process immediate audio children sequentially')
    parser.add_argument('--check-only', action='store_true', help='Validate locally; never upload')
    parser.add_argument('--name')
    parser.add_argument('--allow-low-speech', action='store_true', help='Upload low-speech audio only after explicit user review')
    parser.add_argument('--doctor', action='store_true', help='Check dependencies and command flags without login')
    parser.add_argument('--lark-cli', default=find_cli())
    parser.add_argument('--state-dir', type=Path,
                        default=Path(os.environ.get('RECORDER_STATE_DIR', '~/.recorder-transcribe-v2')).expanduser())
    args = parser.parse_args()
    try:
        if args.doctor:
            report = doctor(args.lark_cli)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if report['ready'] else 1
        if not args.check_only:
            report = doctor(args.lark_cli)
            if not report['ready']:
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return 1
        if not args.path:
            parser.error('path is required unless --doctor is used')
        target = Path(args.path).expanduser().resolve(strict=True)
        files = sorted((p for p in target.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONS), key=lambda p:p.name) if args.batch else [target]
        results, seen = [], set()
        for file in files:
            try:
                effective, _ = resolve_audio(file)
                key = sha256(effective)
                if key in seen:
                    row = {'source': str(file), 'status': 'duplicate'}
                else:
                    seen.add(key)
                    row = process(file, args.state_dir.expanduser().resolve(), Lark(args.lark_cli), args.check_only, args.name, args.allow_low_speech)
            except (WorkflowError, OSError, ValueError) as e:
                row = {'source': str(file), 'status': 'error', 'error': str(e)}
            results.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
        return 1 if any(r['status'] == 'error' for r in results) else 2 if any(r['status'] in ('pending', 'needs_confirm', 'empty_result') for r in results) else 0
    except (WorkflowError, OSError, ValueError) as e:
        print(json.dumps({'status':'error', 'error':str(e)}, ensure_ascii=False))
        return 1

if __name__ == '__main__':
    sys.exit(main())
