"""Local transcription and bounded, chronological speech clip suggestions."""
from dataclasses import dataclass
import math


@dataclass
class Clip:
    start_time: float
    end_time: float
    text: str = ""


def transcribe(path, model_size="small", device="auto", language=None, progress=None):
    import ctranslate2
    from faster_whisper import WhisperModel

    if device not in ("auto", "cpu", "cuda"):
        raise ValueError("Device must be auto, cpu, or cuda")
    selected = device
    if selected == "auto":
        try:
            selected = "cuda" if ctranslate2.get_cuda_device_count() else "cpu"
        except RuntimeError:
            selected = "cpu"

    def run(target):
        model = WhisperModel(model_size, device=target,
                             compute_type="int8_float16" if target == "cuda" else "int8")
        try:
            segments, info = model.transcribe(path, language=language, vad_filter=True,
                                              word_timestamps=True, beam_size=5)
            rows = []
            for segment in segments:
                rows.append({"start": segment.start, "end": segment.end,
                             "text": segment.text.strip(),
                             "words": [{"start": w.start, "end": w.end, "text": w.word}
                                       for w in (segment.words or [])]})
                if progress:
                    progress(min(segment.end / max(info.duration, 1), 1.0))
            return {"segments": rows, "language": info.language, "device": target}
        finally:
            del model

    try:
        result = run(selected)
    except (RuntimeError, OSError) as exc:
        # Inference is lazy: CUDA errors can occur while consuming segments too.
        if device != "auto" or selected != "cuda":
            raise
        if progress:
            progress(0.0)
        result = run("cpu")
        result["warning"] = f"GPU transcription failed; used CPU instead. GPU error: {exc}"
    return result


def suggest_clips(segments, minimum, maximum, duration):
    """Group timestamped speech, respecting limits; omit undersized tails."""
    if not 0 < minimum <= maximum or not math.isfinite(duration) or duration <= 0:
        raise ValueError("Valid duration and positive ordered clip limits are required")
    units = []
    for segment in segments:
        for unit in segment.get("words") or [segment]:
            start, end = float(unit["start"]), float(unit["end"])
            text = unit.get("text", "").strip()
            if not text or not math.isfinite(start) or not math.isfinite(end):
                continue
            start, end = max(0.0, start), min(duration, end)
            while end > start:
                stop = min(end, start + maximum)
                units.append(Clip(start, stop, text))
                start = stop
    units.sort(key=lambda c: c.start_time)
    clips, pending = [], None
    for unit in units:
        if pending and unit.end_time - pending.start_time > maximum:
            if pending.end_time - pending.start_time >= minimum:
                clips.append(pending)
            pending = None
        if pending is None:
            pending = Clip(unit.start_time, unit.end_time, unit.text)
        else:
            pending.end_time = max(pending.end_time, unit.end_time)
            pending.text += " " + unit.text
        if (pending.end_time - pending.start_time >= minimum
                and unit.text.endswith((".", "?", "!", "।"))):
            clips.append(pending)
            pending = None
    if pending and pending.end_time - pending.start_time >= minimum:
        clips.append(pending)
    return clips
