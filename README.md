# 🎬 YouTube Automation Studio

An end-to-end AI-powered video automation suite connecting **yt-dlp**, **Faster-Whisper**, and **Postiz** into a unified local Studio Web Dashboard.

---

## 🚀 Overview

```
 ┌────────────────┐          ┌─────────────────────────┐          ┌────────────────────────┐
 │ 1. yt-dlp      │   ───►   │ 2. Faster-Whisper              │   ───►   │ 3. postiz-app          │
 │ (Downloader)   │          │ (Speech Clips & 9:16)  │          │ (Scheduler / Multi-Post│
 └────────────────┘          └─────────────────────────┘          └────────────────────────┘
  Fetch 1080p+ video          Transcribe with Whisper,            Dispatch to YouTube
  or audio from YouTube       trim, and crop to 9:16 Shorts        Shorts, Reels, TikTok
```

### Integrated Systems
1. **[yt-dlp](yt-dlp/)** — Video and audio downloader with support for YouTube and thousands of media sites.
2. **[clipsai](clipsai/)** — AI video processor that segments videos based on transcript analysis and reformats 16:9 videos to 9:16 vertical shorts with speaker centering.
3. **[postiz-app](postiz-app/)** — Open-source social media management and scheduling platform (Next.js + NestJS + Docker) with support for 28+ channels.
4. **Studio Web UI (`app.py`)** — Streamlit-powered local interactive dashboard that strings the entire workflow together.

---

## ⚡ Quickstart

### 1. Launch the Studio Dashboard
Double-click `run_studio.bat` or run:
```powershell
streamlit run app.py
```
Open **`http://localhost:8501`** in your browser.

### 2. Run Postiz (Social Media Scheduler)
Ensure Docker Desktop is running, then:
```powershell
cd postiz-app
docker compose up -d
```
Open **`http://localhost:4007`** to manage schedules and multi-platform publishing.

---

## 🛠️ Features

- **One-Click Video Ingestion:** Paste YouTube URLs to fetch metadata, thumbnails, and download in 1080p+ MP4 or audio format.
- **Interactive Trimming:** Timeline sliders with duration indicator optimized for YouTube Shorts and TikTok (≤ 60 seconds).
- **9:16 Vertical Reframing:**
  - **Blurred Background Aesthetic:** The popular podcast layout with blurred ambient video borders.
  - **Center Speaker Crop:** Centers the subject in a clean vertical frame.
  - **Original 16:9:** Retains original landscape aspect ratio.
- **Direct Postiz Integration:** Exported MP4s in `exports/` are ready to drag-and-drop or dispatch through Postiz.

## Faster-Whisper transcription

The Studio uses Faster-Whisper without Torch or WhisperX. Use Python 3.10+:

```powershell
python -m pip install -r requirements.txt
```

For the existing uv-managed environment:

```powershell
uv pip install --python .venv/Scripts/python.exe -r requirements.txt
.\run_studio.bat
```

In Tab 2 select **Whisper (Speech-Based Clips)**, choose a model and language,
then click **Transcribe & Find Clips**. The first run downloads the model from
Hugging Face and needs internet access. Later runs use the downloaded model.
`small` is a good GPU starting point; use `base` or `tiny` for faster CPU runs.
All models offered are multilingual, including Hindi support.

Auto mode tries CUDA with `int8_float16`, falling back to CPU INT8 on runtime
failure. Explicit NVIDIA GPU mode reports errors instead of switching devices.
GPU operation requires compatible NVIDIA drivers, CUDA 12 cuBLAS and cuDNN 9
libraries on the library search path; see the
[Faster-Whisper GPU requirements](https://github.com/SYSTRAN/faster-whisper#gpu).
FFmpeg is still required for video rendering.

Results include timestamped transcript JSON and chronological speech clip
suggestions. Suggestions group words within the requested duration limits;
they do not use ClipsAI semantic ranking or predict engagement. Short trailing
speech may be omitted when it cannot meet the minimum duration. Results are
cleared when the source file or transcription settings change, and a failed
run cannot reuse a previous video's clips. Changing clip length reuses the
transcript. No matching clips disables automatic export; use the manual timeline.

Legacy ClipsAI dependencies are preserved separately in
`requirements-clipsai.txt` for optional development and are not required by the
Studio. The bundled ClipsAI source remains available.

## Render multiple selected clips

In Tab 2, use the interactive timeline to set a range and click **Add This
Range to Batch**. Repeat for each desired clip, then choose the entries under
**Select Manual Clips to Render**. No transcription is required for this mode.
Alternatively, after transcription, use **Select Speech Clips to Render**.
Choose one framing style and filename prefix, then click **Render Selected
Clips** to export the selection sequentially. Each MP4 gets a unique batch ID
and clip number in `exports/`. The results table lists successes and failures;
a failed clip does not stop the remaining exports. Source changes clear the
manual queue. The single-range export button remains available in manual mode.
