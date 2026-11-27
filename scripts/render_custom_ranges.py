"""Render the user's thirty exact custom timestamp ranges."""
import json
from pathlib import Path
import re
import shutil
import subprocess
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
RANGES = [
('00:15','00:46'), ('01:13','01:47'), ('01:47','02:20'),
('02:54','03:28'), ('03:28','04:00'), ('04:23','04:58'),
('06:06','06:45'), ('08:35','09:10'), ('10:34','11:09'),
('11:10','11:42'), ('11:43','12:15'), ('13:30','14:02'),
('14:22','14:55'), ('15:53','16:26'), ('17:24','17:58'),
('18:28','19:02'), ('21:54','22:28'), ('23:24','23:56'),
('23:56','24:30'), ('25:21','25:55'), ('26:21','26:55'),
('28:31','29:05'), ('32:33','33:07'), ('35:10','35:45'),
('35:59','36:32'), ('38:36','39:10'), ('42:13','42:47'),
('44:17','44:51'), ('45:32','46:06'), ('46:44','47:18')]
def seconds(value):
    minutes, secs = map(int, value.split(':'))
    return minutes*60 + secs

def main():
    sources = list((ROOT / 'downloads').glob('*LATENT*.mp4'))
    if len(sources) != 1:
        raise RuntimeError('Expected exactly one LATENT episode in downloads')
    source = sources[0]
    ffmpeg, ffprobe = shutil.which('ffmpeg'), shutil.which('ffprobe')
    def probe(path):
        return json.loads(subprocess.check_output([ffprobe, '-v', 'error', '-show_entries',
            'format=duration:stream=codec_type,width,height,duration', '-of', 'json', str(path)], text=True))
    if float(probe(source)['format']['duration']) < seconds(RANGES[-1][1]):
        raise RuntimeError('Source is shorter than the last requested endpoint')
    output = ROOT / 'exports' / ('custom_30_clips_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
    output.mkdir()
    print(f'OUTPUT {output}', flush=True)
    results = []
    # Split the source explicitly; retain the full image over a blurred 9:16 background.
    graph = ('[0:v]split=2[b][f];'
        '[b]scale=180:320:force_original_aspect_ratio=increase,crop=180:320,boxblur=5:5,scale=1080:1920[bg];'
        '[f]scale=1080:1920:force_original_aspect_ratio=decrease[fg];'
        '[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,format=yuv420p[v]')
    for index, (start_label, end_label) in enumerate(RANGES):
        start, end = seconds(start_label), seconds(end_label)
        title = start_label.replace(':','-') + '_to_' + end_label.replace(':','-')
        slug = re.sub(r'[^A-Za-z0-9]+', '_', title).strip('_')
        filename = output / f'{index+1:02d}_{start:04d}-{end:04d}_{slug}.mp4'
        command = [ffmpeg, '-hide_banner', '-loglevel', 'error', '-nostdin', '-n',
            '-ss', str(start), '-i', str(source), '-t', str(end-start), '-filter_complex', graph,
            '-map', '[v]', '-map', '0:a:0', '-c:v', 'h264_nvenc', '-preset', 'p4',
            '-cq', '23', '-b:v', '0', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', str(filename)]
        completed = subprocess.run(command, capture_output=True, text=True)
        if completed.returncode:
            raise RuntimeError(f'Clip {index+1} failed: {completed.stderr}')
        metadata = probe(filename)
        actual = float(metadata['format']['duration'])
        video = next(s for s in metadata['streams'] if s['codec_type']=='video')
        if abs(actual - (end-start)) > 0.15 or (video['width'], video['height']) != (1080,1920):
            raise RuntimeError(f'Output validation failed: {filename}: {metadata}')
        results.append({'clip': index+1, 'title': title, 'start_seconds': start,
            'end_seconds': end, 'duration_seconds': actual, 'file': filename.name})
        (output/'manifest.json').write_text(json.dumps({'source': str(source), 'clips': results}, indent=2), encoding='utf-8')
        print(f'DONE {index+1}/30 | {filename.name} | {actual:.3f}s', flush=True)
    print('COMPLETE: 30 clips validated', flush=True)

if __name__ == '__main__':
    main()
