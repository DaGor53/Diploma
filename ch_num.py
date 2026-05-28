import subprocess
import json

file = input("File name (.mp4): ")

cmd = [
    "ffprobe",
    "-v", "error",
    "-select_streams", "a:0",
    "-show_entries", "stream=channels",
    "-of", "json",
    file
]

result = subprocess.check_output(cmd)
data = json.loads(result)

channels = data["streams"][0]["channels"]

print(f"Audio channels: {channels}")