import subprocess

subprocess.run([
    "ffmpeg",
    "-framerate", "30",
    "-i", "input.h264",
    "-c", "copy",
    "output.mp4"
])

'''
import ffmpeg

(
    ffmpeg
    .input('input.h264', framerate=30)
    .output('output.mp4', vcodec='copy')
    .run()
)
'''