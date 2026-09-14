import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave

SPEC = importlib.util.spec_from_file_location('recorder', Path(__file__).parents[1] / 'skills/recorder-transcribe/scripts/recorder.py')
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)

class Provider:
    def __init__(self, fault=None, pending=False):
        self.calls = []
        self.fault = fault
        self.pending = pending
    def call(self, args, cwd, timeout=360):
        self.calls.append(args[:2])
        if args[:2] == ['drive', '+upload']:
            if self.fault == 'upload': raise m.WorkflowError('upload timeout')
            return {'file_token': 'file123'}
        if args[:2] == ['minutes', '+upload']:
            if self.fault == 'create': raise m.WorkflowError('create timeout')
            return {'minute_token': 'minute123', 'minute_url': 'https://example.feishu.cn/minutes/minute123'}
        if self.fault == 'detail': raise m.WorkflowError('read timeout')
        row = {'minute_token': 'minute123'}
        if self.pending: row.update(status='processing', error='still processing')
        else:
            transcript = Path(cwd) / 'transcript.txt'
            transcript.write_text('Synthetic transcript for a mocked provider, not ASR output.')
            row['artifacts'] = {'transcript_file': str(transcript), 'summary': ''}
        return {'minutes': [row]}

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.audio = self.root / "quote's $recording.wav"
        with wave.open(str(self.audio), 'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
            w.writeframes(b'\0\0' * 32000)
        self.state = self.root / 'state'
    def tearDown(self): self.tmp.cleanup()
    def test_precheck_no_side_effect(self):
        p = Provider()
        self.assertEqual(m.process(self.audio, self.state, p, True)['status'], 'valid')
        self.assertEqual(p.calls, []); self.assertFalse(self.state.exists())
    def test_complete_and_deduplicate(self):
        p = Provider(); before = m.sha256(self.audio)
        self.assertEqual(m.process(self.audio, self.state, p)['status'], 'done')
        self.assertEqual(m.process(self.audio, self.state, p)['status'], 'cached')
        self.assertEqual(len(p.calls), 3); self.assertEqual(before, m.sha256(self.audio))
    def test_ambiguous_create_never_repeated(self):
        p = Provider('create')
        for _ in range(2):
            with self.assertRaises(m.WorkflowError): m.process(self.audio, self.state, p)
        self.assertEqual(p.calls.count(['minutes', '+upload']), 1)
    def test_ambiguous_upload_never_repeated(self):
        p = Provider('upload')
        for _ in range(2):
            with self.assertRaises(m.WorkflowError): m.process(self.audio, self.state, p)
        self.assertEqual(len(p.calls), 1)
    def test_read_failure_resumes_existing_minute(self):
        p = Provider('detail')
        with self.assertRaises(m.WorkflowError): m.process(self.audio, self.state, p)
        p.fault = None
        self.assertEqual(m.process(self.audio, self.state, p)['status'], 'done')
        self.assertEqual(p.calls.count(['minutes', '+upload']), 1)
    def test_processing_is_not_success(self):
        p = Provider(pending=True)
        self.assertEqual(m.process(self.audio, self.state, p)['status'], 'pending')
        p.pending = False
        self.assertEqual(m.process(self.audio, self.state, p)['status'], 'done')
        self.assertEqual(p.calls.count(['drive', '+upload']), 1)
    def test_raw_opus_twin_deduplicates(self):
        raw = self.audio.with_suffix('.opus'); raw.write_bytes(b'KA' * 2000)
        p = Provider()
        m.process(raw, self.state, p)
        self.assertEqual(m.process(self.audio, self.state, p)['status'], 'cached')
    def test_invalid_audio_no_upload(self):
        self.audio.write_bytes(b'')
        p = Provider()
        with self.assertRaises(m.WorkflowError): m.process(self.audio, self.state, p)
        self.assertEqual(p.calls, [])
    def test_corrupt_state_not_reset(self):
        job = self.state / m.sha256(self.audio); job.mkdir(parents=True)
        (job / 'state.json').write_text('broken')
        p = Provider()
        with self.assertRaises(ValueError): m.process(self.audio, self.state, p)
        self.assertEqual(p.calls, [])
    def test_source_changed_before_upload(self):
        p = Provider()
        with patch.object(m.shutil, 'copyfile', side_effect=lambda src,dst: Path(dst).write_bytes(b'changed')):
            with self.assertRaises(m.WorkflowError): m.process(self.audio, self.state, p)
        self.assertEqual(p.calls, [])
    def test_missing_cli_actionable_no_execution(self):
        with patch.object(m.shutil, 'which', return_value=None), patch.object(m, 'run') as run:
            d = m.doctor('missing-cli')
        self.assertFalse(d['ready']); self.assertTrue(any('--install-cli' in x for x in d['next_steps']))
        run.assert_not_called()
    def test_expired_login_blocks(self):
        auth = {'appId': 'example', 'identities': {'user': {'status':'missing','available':False,'scope':' '.join(m.REQUIRED_SCOPES)}}}
        with patch.object(m.shutil, 'which', return_value='/bin/fake'), patch.object(m, 'run', side_effect=['--file --name','--file-token','--minute-tokens --transcript --output-dir',json.dumps(auth)]):
            self.assertFalse(m.doctor('fake')['ready'])
    def test_missing_scope_blocks(self):
        auth = {'appId': 'example', 'identities': {'user': {'status':'ready','available':True,'scope':''}}}
        with patch.object(m.shutil, 'which', return_value='/bin/fake'), patch.object(m, 'run', side_effect=['--file --name','--file-token','--minute-tokens --transcript --output-dir',json.dumps(auth)]):
            d=m.doctor('fake')
        self.assertFalse(d['ready']); self.assertFalse(d['checks']['scopes'])
    def test_provider_error_json_not_success(self):
        with patch.object(m, 'run', return_value='{"ok":false,"error":{"code":123}}'):
            with self.assertRaises(m.WorkflowError): m.Lark().call([], self.root)
    def test_concurrent_run_rejected(self):
        with m.locked(self.state):
            with self.assertRaises(m.WorkflowError):
                with m.locked(self.state): pass

if __name__ == '__main__': unittest.main()
