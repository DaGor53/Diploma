import subprocess
import json
import os

h264_files = [f for f in os.listdir() if f.endswith(".h264")]
wav_files = [f for f in os.listdir() if f.endswith(".wav")]

if not h264_files or not wav_files:
    raise Exception("Не найден .h264 или .wav файл")

input_h264 = h264_files[0]
audio_file = wav_files[0]

temp_mp4 = "temp.mp4"
output_file = "output.mp4"

print(f"Video file: {input_h264}")
print(f"Audio file: {audio_file}")

subprocess.run([
    "ffmpeg",
    "-framerate", "30", 
    "-i", input_h264,
    "-c", "copy",
    temp_mp4
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

video_info = subprocess.check_output([
    "ffprobe",
    "-v", "error",
    "-select_streams", "v:0",
    "-show_entries", "format=duration",
    "-of", "json",
    temp_mp4
])

video_duration = float(json.loads(video_info)["format"]["duration"])

audio_info = subprocess.check_output([
    "ffprobe",
    "-v", "error",
    "-show_entries", "format=duration",
    "-of", "json",
    audio_file
])

audio_duration = float(json.loads(audio_info)["format"]["duration"])

speed = audio_duration / video_duration

print(f"Video: {video_duration:.2f}s")
print(f"Audio: {audio_duration:.2f}s")
print(f"Speed factor: {speed:.4f}")

subprocess.run([
    "ffmpeg",
    "-i", temp_mp4,
    "-i", audio_file,
    "-filter:v", f"setpts={speed}*PTS",
    "-map", "0:v:0",
    "-map", "1:a:0",
    "-c:v", "libx264",
    "-c:a", "aac",
    "-shortest",
    output_file
])

os.remove(temp_mp4)
