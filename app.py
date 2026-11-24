import os
import sys
import subprocess
import json
import re
from pathlib import Path
import streamlit as st

# Setup Paths
BASE_DIR = Path(r"D:\youtube")
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

# Attempt importing clipsai
CLIPS_AI_AVAILABLE = False
CLIPS_AI_ERROR = ""
try:
    if str(CLIPSAI_DIR) not in sys.path:
        sys.path.insert(0, str(CLIPSAI_DIR))
    from clipsai import ClipFinder, Transcriber
    CLIPS_AI_AVAILABLE = True
except Exception as e:
    CLIPS_AI_ERROR = str(e)

FFMPEG_EXE = r"C:\ffmpeg\bin\ffmpeg.exe"
if not os.path.exists(FFMPEG_EXE):
    FFMPEG_EXE = "ffmpeg"  # fallback to PATH


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
    ffprobe_exe = r"C:\ffmpeg\bin\ffprobe.exe"
    if not os.path.exists(ffprobe_exe):
        ffprobe_exe = "ffprobe"

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
        # Blurred background 9:16 pillarbox overlay
        vf = (
            "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,boxblur=25:25[bg];"
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
    '<span class="badge badge-clipsai">ClipsAI</span> Detect & Reframe 9:16 &nbsp;➔&nbsp; '
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
    st.markdown(f"**FFmpeg:** {'✅ Ready' if os.path.exists(FFMPEG_EXE) else '⚠️ Using PATH'}")
    st.markdown(f"**ClipsAI Engine:** {'✅ Core Available' if CLIPS_AI_AVAILABLE else 'ℹ️ Needs Torch/WhisperX'}")

    st.divider()
    st.header("🚀 Postiz Publisher")
    st.markdown("Open your local social media scheduling hub:")
    st.markdown("[👉 Open Postiz Web UI (localhost:4007)](http://localhost:4007)")
    st.caption("Tip: Run `docker compose up -d` in `D:\\youtube\\postiz-app` to start Postiz.")

    st.divider()
    st.header("📂 Folders")
    st.caption(f"**Downloads:** `{DOWNLOADS_DIR}`")
    st.caption(f"**Exported Shorts:** `{EXPORTS_DIR}`")


# ==========================================
# MAIN INTERFACE TABS
# ==========================================
tab_download, tab_clip, tab_publish = st.tabs([
    "1️⃣ Download Video (yt-dlp)",
    "2️⃣ Create & Reframe Short (ClipsAI / FFmpeg)",
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
        st.warning("No downloaded videos found in `D:\\youtube\\downloads`. Download one in Tab 1 or drop a video file into that folder.")

    if selected_video and os.path.exists(selected_video):
        duration = get_video_duration(selected_video)

        col_player, col_controls = st.columns([1, 1])

        with col_player:
            st.markdown("#### Source Video Preview")
            st.video(selected_video)

        with col_controls:
            st.markdown("#### Trimming & Formatting Settings")

            # Dual Mode: Auto AI Highlight vs Interactive Timeline
            mode = st.radio("Highlight Method", ["Interactive Timeline (Instant)", "ClipsAI Engine (Auto-Find)"], horizontal=True)

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

            else:
                st.info("🤖 **ClipsAI** automatically transcribes your audio and uses sentence embeddings to identify stand-alone viral highlights.")
                
                ai_col1, ai_col2 = st.columns([1, 1])
                with ai_col1:
                    whisper_model = st.selectbox("Whisper Model", ["tiny (Fastest)", "base (Balanced)", "small (High Accuracy)"])
                    model_key = whisper_model.split()[0]
                with ai_col2:
                    clip_limits = st.slider("Target Clip Length (Seconds)", 10, 90, (15, 60))

                if st.button("🔍 Run AI Highlight Detection", type="secondary"):
                    with st.spinner("Step 1/2: Transcribing audio with WhisperX (word-level alignment)..."):
                        try:
                            transcriber = Transcriber(model_size=model_key, device="cpu")
                            transcription = transcriber.transcribe(audio_file_path=selected_video)
                            st.session_state['transcription'] = transcription
                            st.success("Transcription complete!")
                        except Exception as e:
                            st.error(f"Transcription error: {e}")

                    if 'transcription' in st.session_state:
                        with st.spinner("Step 2/2: Detecting viral clip boundaries with ClipFinder..."):
                            try:
                                clip_finder = ClipFinder(
                                    min_clip_duration=clip_limits[0],
                                    max_clip_duration=clip_limits[1]
                                )
                                detected = clip_finder.find_clips(transcription=st.session_state['transcription'])
                                st.session_state['detected_clips'] = detected
                                st.success(f"Found {len(detected)} engaging clip segments!")
                            except Exception as e:
                                st.error(f"ClipFinder error: {e}")

                start_s = 0.0
                end_s = min(60.0, float(duration))

                if 'detected_clips' in st.session_state and st.session_state['detected_clips']:
                    clips_list = st.session_state['detected_clips']
                    clip_labels = [
                        f"Clip {i+1}: {format_seconds(c.start_time)} ➔ {format_seconds(c.end_time)} ({c.end_time - c.start_time:.1f}s)"
                        for i, c in enumerate(clips_list)
                    ]
                    chosen_clip_label = st.selectbox("Select Detected Highlight to Export", clip_labels)
                    chosen_idx = clip_labels.index(chosen_clip_label)
                    chosen_clip = clips_list[chosen_idx]
                    start_s = float(chosen_clip.start_time)
                    end_s = float(chosen_clip.end_time)
                    
                    st.success(f"🎯 Selected: {format_seconds(start_s)} to {format_seconds(end_s)} ({end_s - start_s:.1f} seconds)")

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

            if st.button("✨ Render & Export Short Clip", type="primary"):
                output_file = str(EXPORTS_DIR / f"{clip_name}_{aspect_code}.mp4")
                with st.spinner("Rendering clip with FFmpeg high-speed encoder..."):
                    try:
                        rendered_path = render_clip(
                            input_video=selected_video,
                            start_sec=start_s,
                            end_sec=end_s,
                            output_path=output_file,
                            aspect_mode=aspect_code
                        )
                        st.success(f"Rendered Short successfully: `{os.path.basename(rendered_path)}`")
                        st.session_state['last_rendered'] = rendered_path
                    except Exception as err:
                        st.error(f"Render failed: {err}")

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
            """
            ```powershell
            # Run in PowerShell to start Postiz:
            cd D:\\youtube\\postiz-app
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
            st.info("No exported clips found in `D:\\youtube\\exports`. Render a clip in Tab 2!")
