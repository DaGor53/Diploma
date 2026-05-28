import subprocess
import os

file = input("File name (.mp4): ")

m1 = int(input("Start minutes: "))
s1 = int(input("Start seconds: "))

m2 = int(input("End minutes: "))
s2 = int(input("End seconds: "))

start = m1 * 60 + s1
end = m2 * 60 + s2

temp = "temp_cut.mp4"

subprocess.run([
    "ffmpeg",
    "-y",
    "-i", file,
    "-ss", str(start),
    "-to", str(end),
    "-c", "copy",
    temp
])

os.replace(temp, file)

print("Done:", file)