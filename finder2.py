import os
os.environ["YOLO_OFFLINE"] = "True"
import cv2
import json
import numpy as np
import subprocess
import librosa
import matplotlib.pyplot as plt
from ultralytics import YOLO
import sys


FOLDER = os.getcwd()
MODEL_PATH = os.path.join(FOLDER, "last.pt")

TARGET_CLASS = 0        # нужный класс
CONF_THRES = 0.3       # порог уверенности
BATCH_SIZE = 16
FRAME_STEP = 1         # брать каждый 1-й кадр 

SR = 44100
N_MELS = 128

OUT_SPEC = os.path.join(FOLDER, "SPECS")
OUT_JSON = os.path.join(FOLDER, "JSON")

os.makedirs(OUT_SPEC, exist_ok=True)
os.makedirs(OUT_JSON, exist_ok=True)

model = YOLO(MODEL_PATH)

counter = 0

files = [
    "output_3.mp4",
    "output_6.mp4",
    "output_8.mp4",
    "output_9.mp4",
    "output_10.mp4",
    "output_11.mp4",
    "output_12.mp4",
    "output_13.mp4",
    "output_14.mp4",
    "output_15_2.mp4",
    "output_16.mp4",
    "output_17.mp4",
    "output_18.mp4",
]

def extract_audio(video_path, wav_path):
    subprocess.run([
        "ffmpeg", "-y",
        "-i", video_path,
        "-ac", "3",
        wav_path
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def compute_angle(cx, cy, w, h):
    cx0, cy0 = w / 2, h / 2
    dx = cx - cx0
    dy = cy - cy0

    angle = np.degrees(np.arctan2(dy, dx))
    if angle < 0:
        angle += 360
    return angle


def save_mel_png(mel, path):
    plt.imshow(mel, aspect='auto', origin='lower')
    plt.axis('off')
    plt.savefig(path, bbox_inches='tight', pad_inches=0)
    plt.close()

for file in files:
    video_path = os.path.join(FOLDER, file)

    if not os.path.exists(video_path):
        print(f"File not found: {file}")
        continue

    video_path = os.path.join(FOLDER, file)
    audio_path = video_path.replace(".mp4", ".wav")

    print(f"\nProcessing: {file}")

    # --- аудио ---
    extract_audio(video_path, audio_path)
    audio, _ = librosa.load(audio_path, sr=SR, mono=False)

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_sec = total_frames / fps

    batch_frames = []
    batch_ids = []

    frame_id = 0

    while True:
        current_time_sec = frame_id / fps
        ret, frame = cap.read()
        if not ret:
            break

        if frame_id % FRAME_STEP != 0:
            frame_id += 1
            continue

        batch_frames.append(frame)
        batch_ids.append(frame_id)

        if len(batch_frames) == BATCH_SIZE:
            results = model(batch_frames)

            for res, fid, frame in zip(results, batch_ids, batch_frames):

                if res.boxes is None:
                    continue

                for box, cls, conf in zip(res.boxes.xyxy,
                                          res.boxes.cls,
                                          res.boxes.conf):

                    if int(cls) != TARGET_CLASS or conf < CONF_THRES:
                        continue

                    x1, y1, x2, y2 = box.cpu().numpy()

                    area = (x2 - x1) * (y2 - y1)
                    if area < 500:
                        continue

                    cx = (x1 + x2) / 2
                    cy = (y1 + y2) / 2

                    h, w = frame.shape[:2]
                    angle = compute_angle(cx, cy, w, h)

                    t = fid / fps
                    start = int((t - 1) * SR)
                    end = int((t + 1) * SR)

                    start = max(0, start)
                    end = min(audio.shape[1], end)

                    segment = audio[:, start:end]

                    if segment.shape[1] < SR:  # слишком короткий
                        continue

                    mel_channels = []
                    for ch in segment:
                        m = librosa.feature.melspectrogram(
                            y=ch, sr=SR, n_mels=N_MELS)
                        m_db = librosa.power_to_db(m)
                        mel_channels.append(m_db)

                    mel = np.stack(mel_channels)

                    base = f"{file.replace('.mp4','')}_{fid}_{counter}"

                    np.save(os.path.join(OUT_SPEC, base + ".npy"), mel)

                    with open(os.path.join(OUT_JSON, base + ".json"), "w") as f:
                        json.dump({
                            "video": file,
                            "frame": int(fid),
                            "angle": float(angle),
                            "bbox": [float(x1), float(y1), float(x2), float(y2)],
                            "confidence": float(conf)
                        }, f)

                    counter += 1

            batch_frames = []
            batch_ids = []


        if frame_id % (FRAME_STEP * 30) == 0:
            mins = int(current_time_sec // 60)
            secs = int(current_time_sec % 60)

            total_mins = int(duration_sec // 60)
            total_secs = int(duration_sec % 60)

            print(f"[{file}] {mins:02d}:{secs:02d} / {total_mins:02d}:{total_secs:02d}")


        frame_id += 1

    cap.release()

print("\nDone.")
