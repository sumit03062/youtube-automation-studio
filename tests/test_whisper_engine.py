import unittest
from types import SimpleNamespace
from unittest.mock import patch

from whisper_engine import suggest_clips, transcribe


class WhisperTests(unittest.TestCase):
    def test_bounds_and_gaps(self):
        rows = [{"start": 0, "end": 180, "text": "Long speech"},
                {"start": 240, "end": 260, "text": "Next sentence."}]
        clips = suggest_clips(rows, 15, 60, 255)
        self.assertEqual([(c.start_time, c.end_time) for c in clips],
                         [(0, 60), (60, 120), (120, 180), (240, 255)])

    def test_empty_and_short_speech(self):
        self.assertEqual(suggest_clips([], 15, 60, 100), [])
        self.assertEqual(suggest_clips([{"start": 1, "end": 3, "text": "Hi."}], 15, 60, 100), [])

    def test_gpu_lazy_failure_retries_cpu(self):
        calls = []
        class Model:
            def __init__(self, name, device, **kwargs):
                self.device = device
                calls.append(device)
            def transcribe(self, path, **kwargs):
                def segments():
                    if self.device == "cuda":
                        raise RuntimeError("Missing CUDA library")
                    yield SimpleNamespace(start=1, end=20, text="Hello.", words=[])
                return segments(), SimpleNamespace(language="en", duration=20)
        with patch.dict("sys.modules", {
            "ctranslate2": SimpleNamespace(get_cuda_device_count=lambda: 1),
            "faster_whisper": SimpleNamespace(WhisperModel=Model),
        }):
            result = transcribe("video.mp4")
            self.assertEqual(calls, ["cuda", "cpu"])
            self.assertEqual(result["device"], "cpu")
            self.assertEqual(len(result["segments"]), 1)
            with self.assertRaises(RuntimeError):
                transcribe("video.mp4", device="cuda")


if __name__ == "__main__":
    unittest.main()
