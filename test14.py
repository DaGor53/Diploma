import RPi.GPIO as GPIO
import time
import subprocess
from datetime import datetime
import zipfile
import os
import signal

# ================= SETUP =================

BUTTON_PIN = 26
LONG_PRESS_TIME = 1.5

DEVICES = [
    "plughw:CARD=Device,DEV=0",
    "plughw:CARD=Device_1,DEV=0",
    "plughw:CARD=Device_2,DEV=0",
    "plughw:CARD=Device_3,DEV=0",
]

recording = False
process = None
video_process = None
current_file = None
current_video = None
program_start_ts = datetime.now().strftime("%d_%m_%y_%H_%M_%S")
session_id = program_start_ts

# ================= GPIO =================

GPIO.setmode(GPIO.BCM)
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# ================= UTIL =================

def get_timestamp():
    return datetime.now().strftime("%d_%m_%y_%H_%M_%S")

# ================= VIDEO =================

def start_video():
    global video_process, current_video

    timestamp = get_timestamp()

    current_video = f"{session_id}_{timestamp}_vid.h264"

    print(f"Start video ({current_video})")

    video_process = subprocess.Popen([
        "rpicam-vid",
        "-o", current_video,
        "-t", "0",
        "--codec", "h264",
        "--inline",
        "--nopreview"
    ])

    time.sleep(2.0)  # прогрев камеры


def stop_video():
    global video_process

    if video_process:
        print("Stop video...")
        try:
            #video_process.send_signal(2)
            video_process.send_signal(signal.SIGINT)
            video_process.wait(timeout=5)
        except:
            video_process.kill()

        video_process = None

# ================= START =================

def start_recording():
    global process, current_file

    timestamp = get_timestamp()
    current_file = f"{session_id}_{timestamp}_3ch.wav"

    print(f"Start recording ({timestamp})")

    cmd = [
        "gst-launch-1.0", "-q", "-e",
        "interleave", "name=i",

        "alsasrc", "device=" + DEVICES[0], "do-timestamp=true", "buffer-time=200000", "latency-time=10000", "slave-method=none", "!", #slave-method=none добавлено
        "audioconvert", "!", "audioresample", "quality=4", "!", #Изменено quality=0
        "audio/x-raw,format=S16LE,rate=44100,channels=1", "!", #Изменено S16LE
        "queue", "max-size-buffers=0", "max-size-time=0", "max-size-bytes=0", "!", "i.sink_0",

        "alsasrc", "device=" + DEVICES[1], "do-timestamp=true", "buffer-time=200000", "latency-time=10000", "slave-method=none", "!", #slave-method=none добавлено
        "audioconvert", "!", "audioresample", "quality=4", "!", #Изменено quality=0
        "audio/x-raw,format=S16LE,rate=44100,channels=1", "!", #Изменено S16LE
        "queue", "max-size-buffers=0", "max-size-time=0", "max-size-bytes=0", "!", "i.sink_1",  

        "alsasrc", "device=" + DEVICES[2], "do-timestamp=true", "buffer-time=200000", "latency-time=10000", "slave-method=none", "!", #slave-method=none добавлено
        "audioconvert", "!", "audioresample", "quality=4", "!", #Изменено quality=0
        "audio/x-raw,format=S16LE,rate=44100,channels=1", "!", #Изменено S16LE
        "queue", "max-size-buffers=0", "max-size-time=0", "max-size-bytes=0", "!", "i.sink_2",     

        "i.", "!", "wavenc", "!", "filesink", "location=" + current_file
    ]

    process = subprocess.Popen(cmd, stdin=subprocess.PIPE)

# ================= STOP =================

def stop_recording():
    global process

    print("Stop recording...")

    if process:
        try:
            process.send_signal(subprocess.signal.SIGINT)  # мягкая остановка
            process.wait(timeout=5)
        except Exception:
            process.kill()

        process = None

# ================= ARCHIVE =================

def create_archive():

    
    archive_name = f"{session_id}_{get_timestamp()}.zip"

    print(f"Creating archive: {archive_name}")

    kept_files = []

    for f in os.listdir("."):
        if f.startswith(session_id) and f.endswith(".wav"):
            kept_files.append(f)

   # видео
    if current_video and os.path.exists(current_video):
        kept_files.append(current_video)


    if not kept_files:
        print("No files to archive")
        return

    with zipfile.ZipFile(archive_name, "w") as z:
        for f in kept_files:
            z.write(f)

    print("Archive created")

    for f in kept_files:
        try:
            os.remove(f)
            print(f"Deleted: {f}")
        except FileNotFoundError:
            pass

    print("Cleanup done")

# ================= LOOP =================

try:
    while True:
        if GPIO.input(BUTTON_PIN) == GPIO.LOW:
            press_time = time.time()

            while GPIO.input(BUTTON_PIN) == GPIO.LOW:
                time.sleep(0.01)

            duration = time.time() - press_time

            if duration < LONG_PRESS_TIME:
                if not recording:
                    start_video()
                    start_recording()
                    recording = True
                else:
                    stop_video()
                    stop_recording()
                    create_archive()
                    recording = False

            else:
                print("Long press -> exit")

                if recording:
                    stop_video()
                    stop_recording()
                    create_archive()

                break

        time.sleep(0.05)

finally:
    GPIO.cleanup()


