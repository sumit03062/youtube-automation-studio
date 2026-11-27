import os
import sys
import subprocess
import json
import re
from uuid import uuid4
from pathlib import Path
import streamlit as st

# Setup Paths
BASE_DIR = Path(__file__).resolve().parent
YTDLP_DIR = BASE_DIR / "yt-dlp"
CLIPSAI_DIR = BASE_DIR / "clipsai"
DOWNLOADS_DIR = BASE_DIR / "downloads"
EXPORTS_DIR = BASE_DIR / "exports"

DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Add yt-dlp to sys.path so we can import directly
if str(YTDLP_DIR) not in sys.path:
    sys.path.insert(0, str(YTDLP_DIR))

# Attempt importing yt_dlp
try:
    import yt_dlp
    YTDLP_AVAILABLE = True
except Exception as e:
    YTDLP_AVAILABLE = False
    YTDLP_ERROR = str(e)

from whisper_engine import transcribe, suggest_clips

WHISPER_AVAILABLE = False
WHISPER_ERROR = ""
try:
    import faster_whisper
    WHISPER_AVAILABLE = True
except Exception as exc:
    WHISPER_ERROR = str(exc)

import shutil

def find_binary(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        winget_dir = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
        if winget_dir.exists():
            matches = list(winget_dir.glob(f"**/{name}.exe"))
            if matches:
                return str(matches[0])
    standard = Path(r"C:\ffmpeg\bin") / f"{name}.exe"
    if standard.exists():
        return str(standard)
    return name

FFMPEG_EXE = find_binary("ffmpeg")


def get_video_info(url: str):
    """Fetch video metadata using yt-dlp without downloading."""
    ydl_opts = {
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return {
            'title': info.get('title', 'Unknown Title'),
            'duration': info.get('duration', 0),
            'uploader': info.get('uploader', 'Unknown'),
            'thumbnail': info.get('thumbnail', ''),
            'view_count': info.get('view_count', 0),
        }


def download_youtube_video(url: str, output_path: Path, quality: str = "best"):
    """Download video with yt-dlp."""
    if quality == "audio":
        format_spec = "ba[ext=m4a]/ba"
        out_tmpl = str(output_path / "%(title)s.%(ext)s")
    elif quality == "720p":
        format_spec = "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720][ext=mp4]/b"
        out_tmpl = str(output_path / "%(title)s.%(ext)s")
    else:  # best
        format_spec = "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best"
        out_tmpl = str(output_path / "%(title)s.%(ext)s")

    ydl_opts = {
        'format': format_spec,
        'outtmpl': out_tmpl,
        'merge_output_format': 'mp4',
        'ffmpeg_location': FFMPEG_EXE,
        'quiet': False,
        'no_warnings': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        # Ensure mp4 extension if merged
        base, _ = os.path.splitext(filename)
        mp4_path = f"{base}.mp4"
        if os.path.exists(mp4_path):
            return mp4_path
        return filename


def get_video_duration(file_path: str) -> float:
    """Get video duration using ffprobe or ffmpeg."""
    ffprobe_exe = find_binary("ffprobe")

    cmd = [
        ffprobe_exe,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(res.stdout.strip())
    except Exception:
        return 60.0


def render_clip(input_video: str, start_sec: float, end_sec: float, output_path: str, aspect_mode: str):
    """
    Trim and reformat video using ffmpeg:
    - original: keep aspect ratio
    - center_crop: crop to 9:16 vertical centered
    - blurred_bg: 9:16 vertical with blurred background aesthetic
    """
    duration = end_sec - start_sec

    if aspect_mode == "center_crop":
        # 9:16 vertical crop centered
        vf = "crop=ih*9/16:ih:(iw-ow)/2:0,scale=1080:1920"
        cmd = [
            FFMPEG_EXE, "-y",
            "-ss", str(start_sec),
            "-t", str(duration),
            "-i", input_video,
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "22",
            "-c:a", "aac",
            "-b:a", "192k",
            output_path
        ]
    elif aspect_mode == "blurred_bg":
        # High-speed blurred background 9:16 pillarbox overlay (10x faster encoding)
        vf = (
            "[0:v]scale=180:320:force_original_aspect_ratio=increase,"
            "crop=180:320,boxblur=5:5,scale=1080:1920[bg];"
            "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2"
        )
        cmd = [
            FFMPEG_EXE, "-y",
            "-ss", str(start_sec),
            "-t", str(duration),
            "-i", input_video,
            "-filter_complex", vf,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "22",
            "-c:a", "aac",
            "-b:a", "192k",
            output_path
        ]
    else:
        # Original 16:9 or source aspect ratio
        cmd = [
            FFMPEG_EXE, "-y",
            "-ss", str(start_sec),
            "-t", str(duration),
            "-i", input_video,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "22",
            "-c:a", "aac",
            "-b:a", "192k",
            output_path
        ]

    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return output_path


def format_seconds(seconds: float) -> str:
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"


# ==========================================
# STREAMLIT UI CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="YouTube Shorts Studio",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-title {
        font-size: 2.3rem;
        font-weight: 800;
        background: -webkit-linear-gradient(45deg, #FF4B4B, #FF9052);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        color: #888888;
        font-size: 1.05rem;
        margin-bottom: 1.5rem;
    }
    .badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.85rem;
        font-weight: 600;
        margin-right: 8px;
    }
    .badge-ytdlp { background: #FF0000; color: white; }
    .badge-clipsai { background: #6366F1; color: white; }
    .badge-postiz { background: #10B981; color: white; }
    .stTabs [data-baseweb="tab-list"] {
        gap: 12px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">🎬 YouTube Shorts AI Studio</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">'
    '<span class="badge badge-ytdlp">yt-dlp</span> Download Video &nbsp;➔&nbsp; '
    '<span class="badge badge-clipsai">Whisper</span> Transcribe & Reframe 9:16 &nbsp;➔&nbsp; '
    '<span class="badge badge-postiz">Postiz</span> Schedule & Multi-Post'
    '</div>',
    unsafe_allow_html=True
)

# ==========================================
# SIDEBAR
# ==========================================
with st.sidebar:
    st.header("⚙️ Studio Status")
    st.markdown(f"**yt-dlp:** {'✅ Ready' if YTDLP_AVAILABLE else '❌ Error'}")
    st.markdown(f"**FFmpeg:** {'✅ Ready' if os.path.exists(FFMPEG_EXE) or shutil.which(FFMPEG_EXE) else '⚠️ Not Found'}")
    st.markdown(f"**Faster-Whisper:** {'✅ Ready' if WHISPER_AVAILABLE else '⚠️ Installation needed'}")
    if not WHISPER_AVAILABLE:
        st.caption(WHISPER_ERROR)

    st.divider()
    st.header("🚀 Postiz Publisher")
    st.markdown("Open your local social media scheduling hub:")
    st.markdown("[👉 Open Postiz Web UI (localhost:4007)](http://localhost:4007)")
    st.caption(f"Tip: Run `docker compose up -d` in `{BASE_DIR / 'postiz-app'}` to start Postiz.")

    st.divider()
    st.header("📂 Folders")
    st.caption(f"**Downloads:** `{DOWNLOADS_DIR}`")
    st.caption(f"**Exported Shorts:** `{EXPORTS_DIR}`")


# ==========================================
# MAIN INTERFACE TABS
# ==========================================
tab_download, tab_clip, tab_publish = st.tabs([
    "1️⃣ Download Video (yt-dlp)",
    "2️⃣ Create & Reframe Short (Whisper / FFmpeg)",
    "3️⃣ Schedule & Multi-Post (Postiz)"
])

# ------------------------------------------
# TAB 1: DOWNLOAD VIDEO
# ------------------------------------------
with tab_download:
    st.subheader("📥 Download High-Resolution Video")
    st.write("Paste any YouTube link, podcast, interview, or talk to fetch and download.")

    col1, col2 = st.columns([3, 1])
    with col1:
        yt_url = st.text_input("YouTube Video URL", placeholder="https://www.youtube.com/watch?v=...")
    with col2:
        quality = st.selectbox("Format", ["Best Video + Audio (MP4)", "720p (Faster)", "Audio Only (M4A)"])

    quality_map = {
        "Best Video + Audio (MP4)": "best",
        "720p (Faster)": "720p",
        "Audio Only (M4A)": "audio"
    }

    if yt_url:
        try:
            with st.spinner("Fetching video information..."):
                info = get_video_info(yt_url)
                
            info_col1, info_col2 = st.columns([1, 2])
            with info_col1:
                if info.get('thumbnail'):
                    st.image(info['thumbnail'], use_container_width=True)
            with info_col2:
                st.markdown(f"### {info['title']}")
                st.write(f"👤 **Channel:** {info['uploader']}")
                st.write(f"⏱️ **Duration:** {format_seconds(info['duration'])} ({info['duration']} seconds)")
                if info.get('view_count'):
                    st.write(f"👁️ **Views:** {info['view_count']:,}")

            if st.button("⬇️ Download Video to Studio", type="primary"):
                with st.spinner("Downloading video with yt-dlp... this may take a moment."):
                    saved_path = download_youtube_video(yt_url, DOWNLOADS_DIR, quality_map[quality])
                    st.success(f"Downloaded successfully: `{os.path.basename(saved_path)}`")
                    st.session_state['active_video'] = saved_path
                    st.info("Head to Tab 2 ('Create & Reframe Short') to start clipping!")
        except Exception as ex:
            st.error(f"Error fetching/downloading video: {ex}")


# ------------------------------------------
# TAB 2: CLIP & REFRAME TO 9:16
# ------------------------------------------
with tab_clip:
    st.subheader("✂️ Trim, Highlight & Reframe into 9:16 Shorts")

    # List local downloaded files
    available_videos = sorted(
        list(DOWNLOADS_DIR.glob("*.mp4")) + list(DOWNLOADS_DIR.glob("*.mkv")) + list(DOWNLOADS_DIR.glob("*.webm")),
        key=lambda x: x.stat().st_mtime,
        reverse=True
    )

    selected_video = None
    if available_videos:
        video_names = [f.name for f in available_videos]
        default_index = 0
        if 'active_video' in st.session_state:
            active_name = Path(st.session_state['active_video']).name
            if active_name in video_names:
                default_index = video_names.index(active_name)

        chosen_name = st.selectbox("Select Video File to Clip", video_names, index=default_index)
        selected_video = str(DOWNLOADS_DIR / chosen_name)
    else:
        st.warning(f"No downloaded videos found in `{DOWNLOADS_DIR}`. Download one in Tab 1 or drop a video file into that folder.")

    if selected_video and os.path.exists(selected_video):
        duration = get_video_duration(selected_video)

        col_player, col_controls = st.columns([1, 1])

        with col_player:
            st.markdown("#### Source Video Preview")
            st.video(selected_video)

        with col_controls:
            st.markdown("#### Trimming & Formatting Settings")

            source_stat = Path(selected_video).stat()
            batch_source = (selected_video, source_stat.st_size, source_stat.st_mtime_ns)
            if st.session_state.get("batch_source") != batch_source:
                st.session_state["batch_source"] = batch_source
                st.session_state["manual_clips"] = []
                st.session_state.pop("batch_results", None)
                st.session_state.pop("manual_selection", None)
            batch_clips = []

            # Choose manual timestamps or transcript-based clips
            mode = st.radio("Highlight Method", ["Interactive Timeline (Instant)", "Whisper (Speech-Based Clips)"], horizontal=True)

            if mode == "Interactive Timeline (Instant)":
                st.caption(f"Total Video Length: **{format_seconds(duration)}** ({duration:.1f}s)")
                
                time_range = st.slider(
                    "Select Start & End Time (Seconds)",
                    min_value=0.0,
                    max_value=float(duration),
                    value=(0.0, min(60.0, float(duration))),
                    step=0.5
                )
                start_s, end_s = time_range
                clip_dur = end_s - start_s
                
                # Indicator badge for shorts duration
                if clip_dur <= 60:
                    st.success(f"⏱️ Selected Duration: **{clip_dur:.1f}s** (Optimal for YouTube Shorts, TikTok, Reels)")
                else:
                    st.warning(f"⏱️ Selected Duration: **{clip_dur:.1f}s** (Note: YouTube Shorts max is 60s)")

                if st.button("Add This Range to Batch", disabled=end_s <= start_s):
                    queue = st.session_state["manual_clips"]
                    if (start_s, end_s) not in queue:
                        queue.append((start_s, end_s))
                        st.session_state["manual_selection"] = list(range(len(queue)))
                queue = st.session_state["manual_clips"]
                selected_ranges = st.multiselect("Select Manual Clips to Render", range(len(queue)),
                    key="manual_selection",
                    format_func=lambda i: f"Clip {i+1}: {format_seconds(queue[i][0])} to {format_seconds(queue[i][1])}")
                batch_clips = [(i+1, *queue[i]) for i in selected_ranges]
                st.caption("Choose each range on the timeline and add it to the batch. Select the clips you want, then render them together below.")

            else:
                st.info("Whisper transcribes speech and suggests chronological clips using speech boundaries. Suggestions are not ranked by engagement.")
                model_key = st.selectbox("Whisper Model", ["tiny", "base", "small"], index=2)
                device_label = st.selectbox("Processing Device", ["Auto (GPU with CPU fallback)", "CPU", "NVIDIA GPU"])
                device = {"Auto (GPU with CPU fallback)": "auto", "CPU": "cpu", "NVIDIA GPU": "cuda"}[device_label]
                language_label = st.selectbox("Speech Language", ["Auto-detect", "Hindi", "English"])
                language = {"Auto-detect": None, "Hindi": "hi", "English": "en"}[language_label]
                clip_limits = st.slider("Target Clip Length (Seconds)", 10, 90, (15, 60))
                st.caption("The first run downloads the model. Small is recommended for your GPU; base is faster on CPU.")
                source = Path(selected_video).stat()
                request_key = (selected_video, source.st_size, source.st_mtime_ns, model_key, device, language)
                if st.session_state.get("whisper_key") != request_key:
                    st.session_state.pop("whisper_result", None)
                    st.session_state.pop("whisper_key", None)
                if not WHISPER_AVAILABLE:
                    st.warning("Install dependencies using: python -m pip install -r requirements.txt")
                if st.button("🔍 Transcribe & Find Clips", disabled=not WHISPER_AVAILABLE):
                    st.session_state.pop("whisper_result", None)
                    st.session_state.pop("whisper_key", None)
                    progress_bar = st.progress(0.0)
                    try:
                        with st.spinner("Transcribing speech with Faster-Whisper..."):
                            result = transcribe(selected_video, model_key, device, language, progress_bar.progress)
                        st.session_state["whisper_result"] = result
                        st.session_state["whisper_key"] = request_key
                    except Exception as exc:
                        st.error(f"Transcription failed: {exc}. Try CPU mode if CUDA libraries are unavailable.")
                    finally:
                        progress_bar.empty()

                start_s, end_s = 0.0, min(60.0, float(duration))
                result = st.session_state.get("whisper_result")
                if result:
                    if result.get("warning"):
                        st.warning(result["warning"])
                    st.caption(f"Language: {result['language']} | Processing device: {result['device']}")
                    clips_list = suggest_clips(result["segments"], *clip_limits, duration) if duration > 0 else []
                    if clips_list:
                        selection_signature = (request_key, tuple((c.start_time, c.end_time) for c in clips_list))
                        if st.session_state.get("speech_selection_signature") != selection_signature:
                            st.session_state.pop("speech_selection", None)
                            st.session_state["speech_selection_signature"] = selection_signature
                        chosen_indices = st.multiselect("Select Speech Clips to Render", range(len(clips_list)),
                            key="speech_selection",
                            format_func=lambda i: f"Clip {i+1}: {format_seconds(clips_list[i].start_time)} to {format_seconds(clips_list[i].end_time)}")
                        batch_clips = [(i+1, clips_list[i].start_time, clips_list[i].end_time) for i in chosen_indices]
                        for i in chosen_indices:
                            with st.expander(f"Clip {i+1} transcript"):
                                st.write(clips_list[i].text)
                    else:
                        st.warning("No speech clips fit these limits. Adjust the limits or use the interactive timeline.")
                    with st.expander("Transcript with timestamps"):
                        st.dataframe([{k: row[k] for k in ("start", "end", "text")} for row in result["segments"]])
                    st.download_button("Download transcript JSON", json.dumps(result, ensure_ascii=False, indent=2),
                                       file_name=Path(selected_video).stem + ".transcript.json", mime="application/json")

            st.markdown("#### Aspect Ratio & Styling")
            aspect_choice = st.selectbox(
                "Output Framing Format",
                [
                    "9:16 Vertical (Blurred Background Aesthetic - Recommended for Podcasts)",
                    "9:16 Vertical (Center Crop)",
                    "Original (16:9 Landscape)"
                ]
            )

            aspect_code = "blurred_bg"
            if "Center Crop" in aspect_choice:
                aspect_code = "center_crop"
            elif "Original" in aspect_choice:
                aspect_code = "original"

            clip_name = st.text_input("Short Clip Title / Filename", value="short_clip_1")

            safe_name = re.sub(r'[^\w-]+', '_', clip_name).strip('_')[:80] or "short"
            if mode == "Interactive Timeline (Instant)":
                if st.button("✨ Render & Export Short Clip", disabled=duration <= 0 or end_s <= start_s):
                    output_file = str(EXPORTS_DIR / f"{safe_name}_{uuid4().hex[:10]}_{aspect_code}.mp4")
                    with st.spinner("Rendering clip..."):
                        try:
                            st.session_state['last_rendered'] = render_clip(selected_video, start_s, end_s, output_file, aspect_code)
                            st.success("Clip exported successfully.")
                        except Exception as err:
                            st.error(f"Render failed: {err}")

            st.caption(f"{len(batch_clips)} clips selected for batch export. The framing above applies to all selected clips.")
            if st.button("🎬 Render Selected Clips", type="primary", disabled=not batch_clips or duration <= 0):
                batch_id = uuid4().hex[:10]
                results = []
                progress = st.progress(0.0)
                for position, (number, clip_start, clip_end) in enumerate(batch_clips):
                    output_file = str(EXPORTS_DIR / f"{safe_name}_{batch_id}_clip_{number:02d}_{aspect_code}.mp4")
                    with st.spinner(f"Rendering clip {position+1} of {len(batch_clips)}..."):
                        try:
                            if not 0 <= clip_start < clip_end <= duration:
                                raise ValueError("Clip timestamps fall outside the source video")
                            path = render_clip(selected_video, clip_start, clip_end, output_file, aspect_code)
                            results.append({"clip": number, "file": path, "status": "Exported"})
                            st.session_state['last_rendered'] = path
                        except Exception as err:
                            Path(output_file).unlink(missing_ok=True)
                            results.append({"clip": number, "file": "", "status": f"Failed: {err}"})
                    progress.progress((position+1)/len(batch_clips))
                st.session_state["batch_results"] = results
                progress.empty()
            if st.session_state.get("batch_results"):
                results = st.session_state["batch_results"]
                completed = sum(r["status"] == "Exported" for r in results)
                st.info(f"Last batch: {completed}/{len(results)} clips exported to {EXPORTS_DIR}")
                st.dataframe(results, hide_index=True)

        # Show preview of rendered short
        if 'last_rendered' in st.session_state and os.path.exists(st.session_state['last_rendered']):
            st.divider()
            st.markdown("### 📱 Rendered Vertical Short Preview")
            col_preview, col_actions = st.columns([1, 2])
            with col_preview:
                st.video(st.session_state['last_rendered'])
            with col_actions:
                st.markdown("#### Ready for Distribution!")
                st.write(f"📁 **Saved to:** `{st.session_state['last_rendered']}`")
                st.markdown("Click **Tab 3 ('Schedule & Multi-Post')** to upload to Postiz and publish to YouTube, TikTok, and Instagram!")


# ------------------------------------------
# TAB 3: PUBLISH WITH POSTIZ
# ------------------------------------------
with tab_publish:
    st.subheader("🚀 Postiz Social Media Dispatcher")
    st.write(
        "Postiz allows you to schedule and publish your generated Shorts across **YouTube Shorts, "
        "TikTok, Instagram Reels, LinkedIn, Twitter/X**, and 20+ other platforms from one calendar."
    )

    col_p1, col_p2 = st.columns([1, 1])

    with col_p1:
        st.markdown("#### 1. Launch Postiz")
        st.write("Postiz runs locally in Docker containers at port `4007`.")
        
        st.markdown(
            f"""
            ```powershell
            # Run in PowerShell to start Postiz:
            cd {BASE_DIR / 'postiz-app'}
            docker compose up -d
            ```
            """
        )
        
        st.link_button("🌐 Open Postiz Dashboard (http://localhost:4007)", "http://localhost:4007", type="primary")

    with col_p2:
        st.markdown("#### 2. Exported Shorts Ready to Post")
        exported_files = sorted(
            list(EXPORTS_DIR.glob("*.mp4")),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )

        if exported_files:
            for ef in exported_files[:5]:
                with st.expander(f"🎬 {ef.name} ({ef.stat().st_size / (1024*1024):.1f} MB)"):
                    st.caption(f"Path: `{ef}`")
                    st.video(str(ef))
        else:
            st.info(f"No exported clips found in `{EXPORTS_DIR}`. Render a clip in Tab 2!")
