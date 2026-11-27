"""Render the user's thirty exact, consecutive 30-second ranges."""
import json
from pathlib import Path
import re
import shutil
import subprocess
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
TITLES = '''Season Finale and 1 Lakh Rule
Nostalgic Panel Intro
Marriage and Past Jokes
Keshavs Return and Poetry
Romantic Verse Highlight
Glow-Up and Past Reactions
Hindi and Western Culture Talk
Hindi Word Debate
Book Gift and Store Plug
Boss R15 Enters and Opens
Heartbreak Shayari
First Fan Recognition Story
Engagement Twist
Karwa Chauth Shayari
Job and Bike Promise
Work-From-Home and Phones
Tony Kakkar Phone Call
Folk-Jamaican Mix Intro
Crowd Chant and Rhythm
Two Years Later and Shyness
Starbucks Date Roleplay
Chai Stall Roleplay
Train Vendor Roleplay
Climax and Final Shayari
Bonus Home and Open Mics
Moving to Mumbai and Accents
Legal Notices and Viral Clips
Resolving an Old Dispute
Samays Comeback Reflection
Brotherhood and Season Finale Outro'''.splitlines()

def main():
    sources = list((ROOT / 'downloads').glob('*LATENT*.mp4'))
    if len(sources) != 1:
        raise RuntimeError('Expected exactly one LATENT episode in downloads')
    source = sources[0]
    ffmpeg, ffprobe = shutil.which('ffmpeg'), shutil.which('ffprobe')
    def probe(path):
        return json.loads(subprocess.check_output([ffprobe, '-v', 'error', '-show_entries',
            'format=duration:stream=codec_type,width,height,duration', '-of', 'json', str(path)], text=True))
    if float(probe(source)['format']['duration']) < 900:
        raise RuntimeError('Source must contain all 900 requested seconds')
    output = ROOT / 'exports' / ('requested_30_clips_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
    output.mkdir()
    print(f'OUTPUT {output}', flush=True)
    results = []
    # Split the source explicitly; retain the full image over a blurred 9:16 background.
    graph = ('[0:v]split=2[b][f];'
        '[b]scale=180:320:force_original_aspect_ratio=increase,crop=180:320,boxblur=5:5,scale=1080:1920[bg];'
        '[f]scale=1080:1920:force_original_aspect_ratio=decrease[fg];'
        '[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,format=yuv420p[v]')
    for index, title in enumerate(TITLES):
        start, end = index*30, (index+1)*30
        slug = re.sub(r'[^A-Za-z0-9]+', '_', title).strip('_')
        filename = output / f'{index+1:02d}_{start:04d}-{end:04d}_{slug}.mp4'
        command = [ffmpeg, '-hide_banner', '-loglevel', 'error', '-nostdin', '-n',
            '-ss', str(start), '-i', str(source), '-t', '30', '-filter_complex', graph,
            '-map', '[v]', '-map', '0:a:0', '-c:v', 'h264_nvenc', '-preset', 'p4',
            '-cq', '23', '-b:v', '0', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', str(filename)]
        completed = subprocess.run(command, capture_output=True, text=True)
        if completed.returncode:
            raise RuntimeError(f'Clip {index+1} failed: {completed.stderr}')
        metadata = probe(filename)
        actual = float(metadata['format']['duration'])
        video = next(s for s in metadata['streams'] if s['codec_type']=='video')
        if abs(actual - 30) > 0.15 or (video['width'], video['height']) != (1080,1920):
            raise RuntimeError(f'Output validation failed: {filename}: {metadata}')
        results.append({'clip': index+1, 'title': title, 'start_seconds': start,
            'end_seconds': end, 'duration_seconds': actual, 'file': filename.name})
        (output/'manifest.json').write_text(json.dumps({'source': str(source), 'clips': results}, indent=2), encoding='utf-8')
        print(f'DONE {index+1}/30 | {filename.name} | {actual:.3f}s', flush=True)
    print('COMPLETE: 30 clips validated', flush=True)

if __name__ == '__main__':
    main()
