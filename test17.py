import RPi.GPIO as GPIO
import time
import subprocess
import os
import numpy as np

from scipy.io import wavfile
import tflite_runtime.interpreter as tflite
from scipy.signal import spectrogram

def hz_to_mel(hz):
    return 2595 * np.log10(1 + hz / 700)

def mel_to_hz(mel):
    return 700 * (10**(mel / 2595) - 1)

def create_mel_filterbank(
    sr,
    n_fft=512,
    n_mels=128,
    fmin=0,
    fmax=None
):

    if fmax is None:
        fmax = sr / 2

    # =============================================
    # MEL POINTS
    # =============================================

    mel_min = hz_to_mel(fmin)
    mel_max = hz_to_mel(fmax)

    mel_points = np.linspace(
        mel_min,
        mel_max,
        n_mels + 2
    )

    hz_points = mel_to_hz(mel_points)

    # FFT bins
    bins = np.floor(
        (n_fft + 1) * hz_points / sr
    ).astype(int)

    # =============================================
    # FILTERBANK
    # =============================================

    fb = np.zeros((n_mels, n_fft // 2 + 1))

    for m in range(1, n_mels + 1):

        f_m_minus = bins[m - 1]
        f_m = bins[m]
        f_m_plus = bins[m + 1]

        # left slope
        for k in range(f_m_minus, f_m):
            fb[m - 1, k] = (
                (k - f_m_minus)
                / (f_m - f_m_minus + 1e-8)
            )

        # right slope
        for k in range(f_m, f_m_plus):
            fb[m - 1, k] = (
                (f_m_plus - k)
                / (f_m_plus - f_m + 1e-8)
            )

    return fb


# =========================================================
# GPIO
# =========================================================

BUTTON_PIN = 26
LONG_PRESS_TIME = 1.5

GPIO.setmode(GPIO.BCM)
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# =========================================================
# AUDIO DEVICES
# =========================================================

DEVICES = [
    "plughw:CARD=Device,DEV=0",
    "plughw:CARD=Device_1,DEV=0",
    "plughw:CARD=Device_2,DEV=0",
]

running = False

# =========================================================
# LOAD AUDIO MODEL
# =========================================================

audio_interpreter = tflite.Interpreter(
    model_path="model1.tflite"
)

audio_interpreter.allocate_tensors()

audio_input_details = audio_interpreter.get_input_details()
audio_output_details = audio_interpreter.get_output_details()

# =========================================================
# AUDIO RECORDING
# =========================================================

def record_audio_chunk():

    filename = "/tmp/audio_chunk.wav"

    if os.path.exists(filename):
        os.remove(filename)

    cmd = [

        "gst-launch-1.0",
        "-q",
        "-e",

        "interleave",
        "name=i",

        # =================================================
        # MIC 1
        # =================================================

        "alsasrc",
        "device=" + DEVICES[0],
        "num-buffers=50",
        "do-timestamp=true",
        "buffer-time=200000",
        "latency-time=10000",
        "slave-method=none",
        "!",

        "audioconvert",
        "!",

        "audioresample",
        "quality=4",
        "!",

        "audio/x-raw,format=S16LE,rate=16000,channels=1",
        "!",

        "queue",
        "!",
        "i.sink_0",

        # =================================================
        # MIC 2
        # =================================================

        "alsasrc",
        "device=" + DEVICES[1],
        "num-buffers=50",
        "do-timestamp=true",
        "buffer-time=200000",
        "latency-time=10000",
        "slave-method=none",
        "!",

        "audioconvert",
        "!",

        "audioresample",
        "quality=4",
        "!",

        "audio/x-raw,format=S16LE,rate=16000,channels=1",
        "!",

        "queue",
        "!",
        "i.sink_1",

        # =================================================
        # MIC 3
        # =================================================

        "alsasrc",
        "device=" + DEVICES[2],
        "num-buffers=50",
        "do-timestamp=true",
        "buffer-time=200000",
        "latency-time=10000",
        "slave-method=none",
        "!",

        "audioconvert",
        "!",

        "audioresample",
        "quality=4",
        "!",

        "audio/x-raw,format=S16LE,rate=16000,channels=1",
        "!",

        "queue",
        "!",
        "i.sink_2",

        # =================================================
        # OUTPUT
        # =================================================

        "i.",
        "!",
        "wavenc",
        "!",
        "filesink",
        "location=" + filename
    ]

    subprocess.run(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    return filename

def load_audio(filename):

    sr, audio = wavfile.read(filename)
    audio = audio.astype(np.float32)

    # int16 -> float32
    audio /= 32768.0

    return sr, audio

mel_filterbank = create_mel_filterbank(
    sr=16000,
    n_fft=512,
    n_mels=128
)

def preprocess_audio(audio, sr):
    mels = []
    for ch in range(3):
        signal = audio[:, ch]
        freqs, times, spec = spectrogram(
            signal,
            fs=sr,
            nperseg=512,
            noverlap=256,
            mode='magnitude'
        )

        mel_spec = np.dot(
            mel_filterbank,
            spec
        )

        mel_spec = np.log(
            mel_spec + 1e-8
        )

        T = 128

        if mel_spec.shape[1] > T:

            mel_spec = mel_spec[:, :T]

        else:

            pad = T - mel_spec.shape[1]

            mel_spec = np.pad(
                mel_spec,
                ((0,0),(0,pad))
            )

        mels.append(mel_spec)

    x = np.stack(mels, axis=-1)
    x = np.expand_dims(x, axis=0)
    x = x.astype(np.float32)

    return x

# =========================================================
# AUDIO INFERENCE
# =========================================================

def predict_audio():

    filename = record_audio_chunk()

    sr, audio = load_audio(filename)

    os.remove(filename)

    x = preprocess_audio(audio, sr)

    audio_interpreter.set_tensor(
        audio_input_details[0]['index'],
        x
    )

    audio_interpreter.invoke()

    output = audio_interpreter.get_tensor(
        audio_output_details[0]['index']
    )[0]

    detected_score = float(output[0])

    sin_val = float(output[1])
    cos_val = float(output[2])

    detected = detected_score < 0.35

    if detected:
        angle = np.degrees(np.arctan2(sin_val, cos_val))
        if angle < 0:
            angle += 360
        angle = float(angle)
    else:
        angle = None

    return {
        "detected": detected,
        "score": detected_score,
        "angle": angle,
        "sin": sin_val,
        "cos": cos_val
    }

# =========================================================
# START / STOP
# =========================================================

def start_system():
    global running
    running = True
    print("SYSTEM STARTED")

def stop_system():
    global running
    running = False
    print("SYSTEM STOPPED")

# =========================================================
# MAIN LOOP
# =========================================================

try:
    while True:
        if GPIO.input(BUTTON_PIN) == GPIO.LOW:

            press_time = time.time()

            while GPIO.input(BUTTON_PIN) == GPIO.LOW:
                time.sleep(0.01)

            duration = time.time() - press_time

            if duration < LONG_PRESS_TIME:
                if not running:
                    start_system()
                else:
                    stop_system()
            else:
                print("EXIT")
                break

        if running:

            try:

                audio_result = predict_audio()

                print("\nAUDIO MODEL:")

                print(
                    f"Detected: {audio_result['detected']} "
                    f"(score={audio_result['score']:.3f})"
                )

                if audio_result["detected"]:
                    print(
                        f"Angle={audio_result['angle']:.1f}° "
                        f"sin={audio_result['sin']:.3f} "
                        f"cos={audio_result['cos']:.3f}"
                    )
                else:
                    print("Angle=None")

            except Exception as e:
                print("Audio inference error:", e)
            print("\n" + "="*50 + "\n")
        time.sleep(0.1)

finally:
    GPIO.cleanup()