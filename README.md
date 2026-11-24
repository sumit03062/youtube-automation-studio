# 🎬 YouTube Automation Studio

An end-to-end AI-powered video automation suite connecting **yt-dlp**, **ClipsAI**, and **Postiz** into a unified local Studio Web Dashboard.

---

## 🚀 Overview

```
 ┌────────────────┐          ┌─────────────────────────┐          ┌────────────────────────┐
 │ 1. yt-dlp      │   ───►   │ 2. clipsai              │   ───►   │ 3. postiz-app          │
 │ (Downloader)   │          │ (AI Highlights & 9:16)  │          │ (Scheduler / Multi-Post│
 └────────────────┘          └─────────────────────────┘          └────────────────────────┘
  Fetch 1080p+ video          Transcribe with WhisperX,            Dispatch to YouTube      
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
