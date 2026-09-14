#!/usr/bin/env python3
"""Local Silero ONNX speech screening. Audio is never sent to a service."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

MODEL_SHA256 = '1a153a22f4509e292a94e67d6f9b85e8deb25b4988682b7e174c65279d8788e3'
MODEL_URL = 'https://raw.githubusercontent.com/snakers4/silero-vad/867c2aa692646a1f1de3e94a15c9dd9f614c0acb/src/silero_vad/data/silero_vad.onnx'
MODEL = Path.home() / '.local/share/recorder-transcribe/silero_vad.onnx'


def session():
    import onnxruntime as ort
    if hashlib.sha256(MODEL.read_bytes()).hexdigest() != MODEL_SHA256:
        raise ValueError('VAD model checksum mismatch')
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 1
    opts.inter_op_num_threads = 1
    return ort.InferenceSession(str(MODEL), sess_options=opts, providers=['CPUExecutionProvider'])


def analyze(file):
    import numpy as np
    model = session()
    with tempfile.TemporaryDirectory(prefix='recorder-vad-') as d:
        pcm = Path(d) / 'audio.pcm'
        p = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-xerror', '-i', str(file),
                            '-map', '0:a:0', '-vn', '-ac', '1', '-ar', '16000', '-f', 's16le', str(pcm)],
                           capture_output=True, timeout=300)
        if p.returncode:
            raise ValueError('Cannot decode audio for speech screening')
        state = np.zeros((2, 1, 128), dtype=np.float32)
        context = np.zeros((1, 64), dtype=np.float32)
        samples = 0
        speech_samples = 0
        run_samples = 0
        with pcm.open('rb') as f:
            while True:
                raw = f.read(1024)
                if not raw: break
                chunk = np.frombuffer(raw, dtype='<i2').astype(np.float32) / 32768
                size = len(chunk)
                samples += size
                chunk = np.pad(chunk, (0, 512 - size)).reshape(1, 512)
                frame = np.concatenate((context, chunk), axis=1)
                out, state = model.run(None, {'input':frame, 'state':state, 'sr':np.array(16000,dtype=np.int64)})
                context = frame[:, -64:]
                if float(out[0][0]) >= 0.5:
                    run_samples += size
                else:
                    if run_samples >= 4000: speech_samples += run_samples
                    run_samples = 0
        if run_samples >= 4000: speech_samples += run_samples
        if samples == 0: raise ValueError('No decoded samples')
        return {'speech_seconds': round(speech_samples / 16000, 3),
                'speech_ratio': round(speech_samples / samples, 6),
                'analyzed_seconds': round(samples / 16000, 3),
                'method':'silero-onnx', 'threshold':0.5, 'min_run_seconds':0.25}

if __name__ == '__main__':
    try:
        if sys.argv[1:] == ['--check']:
            session(); print(json.dumps({'ready':True}))
        else: print(json.dumps(analyze(Path(sys.argv[1]))))
    except Exception as e:
        print(json.dumps({'error':str(e)})); sys.exit(1)
