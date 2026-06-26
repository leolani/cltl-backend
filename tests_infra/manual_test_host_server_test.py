try:
    import matplotlib.pyplot as plt
except ImportError as e:
    print("Manually install: pip install matplotlib")
    raise e

import argparse
import io
import logging
import struct
import wave

import numpy as np
import requests
import sounddevice as sd
import soundfile

from cltl.backend.api.camera import CameraResolution
from cltl.backend.server import BackendServer
from cltl.backend.source.client_source import ClientAudioSource, ClientImageSource

logger = logging.getLogger(__name__)


def run_host_server(port):
    server = BackendServer(sampling_rate=16000, channels=1, frame_size=480,
                           camera_resolution=CameraResolution.QVGA, camera_index=0)
    server.run('0.0.0.0', port)


def test_mic(server_url, duration=10, store=False):
    source = ClientAudioSource(f"{server_url}/audio")

    while True:
        with source as mic:
            snippet = []
            for _ in range((1000//30) * duration):
                snippet.append(next(mic.audio))
            store_wav(mic.audio, source.rate, store)


def test_image(server_url):
    source = ClientImageSource(f"{server_url}/image")

    inp = None
    while inp != "q":
        with source as cam:
            image = cam.capture().image
            print("Captured image: ", image.shape)
            plt.imshow(image)
            plt.show()
        inp = input("Press enter to continue, q to quit:")


def test_sound(server_url, wav_path=None):
    if wav_path:
        with open(wav_path, 'rb') as f:
            wav_bytes = f.read()
    else:
        # Generate a short 440 Hz tone as a fallback when no file is provided.
        rate, duration_ms = 16000, 500
        num_frames = rate * duration_ms // 1000
        tone = [int(32767 * 0.3 * __import__('math').sin(2 * __import__('math').pi * 440 * i / rate))
                for i in range(num_frames)]
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(rate)
            wf.writeframes(struct.pack(f'<{num_frames}h', *tone))
        wav_bytes = buf.getvalue()

    response = requests.post(f"{server_url}/sound", data=wav_bytes,
                             headers={'Content-Type': 'audio/wav'})
    print(f"POST /sound -> {response.status_code}")
    if response.status_code != 200:
        print(f"Error: {response.text}")


def test_tts(server_url, text=None):
    if not text:
        text = "Hello Stranger!"
    requests.post(f"{server_url}/tts", text)


def store_wav(frames, sampling_rate, save=None):
    if not isinstance(frames, np.ndarray):
        audio = np.concatenate(frames)
    else:
        audio = frames
    if save:
        soundfile.write(save, audio, sampling_rate)
    else:
        print(audio.shape)
        sd.play(audio, sampling_rate)
        sd.wait()


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    epilog = """
        To test the server manually start the server by running
            > python manual_test_host_server_test.py --server
        and in another terminal test the individual modalities by running e.g.
            > python manual_test_host_server_test.py --modality audio
        """

    parser = argparse.ArgumentParser(description='Test backend servers', epilog=epilog)

    parser.add_argument('--modality', type=str, choices=["audio", "image", "sound"], default="image", help="Choose a modality to test.")
    parser.add_argument('--wav', type=str, default=None, help="Path to a WAV file to send to /sound (generates a tone if omitted).")
    parser.add_argument('--server', action='store_true', help="Run the host server")
    parser.add_argument('--port', type=int, default="5000", help="Port to use.")
    args, _ = parser.parse_known_args()

    logger.info("Starting webserver with args: %s", args)

    if args.server:
        run_host_server(args.port)
    elif args.modality == "text":
        server_url = f"http://localhost:{args.port}"
        test_tts(server_url)
    elif args.modality == "audio":
        server_url = f"http://localhost:{args.port}"
        test_mic(server_url)
    elif args.modality == "image":
        server_url = f"http://localhost:{args.port}"
        test_image(server_url)
    elif args.modality == "sound":
        server_url = f"http://localhost:{args.port}"
        test_sound(server_url, args.wav)