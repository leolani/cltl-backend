try:
    import matplotlib.pyplot as plt
except ImportError as e:
    print("Manually install: pip install matplotlib")
    raise e

import argparse
import logging

import numpy as np
import requests
import sounddevice as sd
import soundfile

from cltl.backend.api.camera import CameraResolution
from cltl.backend.source.client_source import ClientAudioSource, ClientImageSource
from host.server import BackendServer

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
    source = ClientImageSource(f"{server_url}/video")

    inp = None
    while inp != "q":
        with source as cam:
            image = cam.capture().image
            print("Captured image: ", image.shape)
            plt.imshow(image)
            plt.show()
        inp = input("Press enter to continue, q to quit:")


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

    parser = argparse.ArgumentParser(description='Test backend servers')
    parser.add_argument('--modality', type=str, choices=["audio", "image"], default="image", help="Choose a modality to test.")
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