import argparse
import logging

from flask import Flask

from host.server import backend_server


logger = logging.getLogger(__name__)


app = Flask(__name__)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    parser = argparse.ArgumentParser(description='Backend application to serve sensor data from a host machine')
    parser.add_argument('--rate', type=int, choices=[16000, 32000, 44100], default=16000, help="Sampling rate.")
    parser.add_argument('--channels', type=int, choices=[1, 2], default=2, help="Number of audio channels.")
    parser.add_argument('--frame_duration', type=int, choices=[10, 20, 30], default=30, help="Duration of audio frames in milliseconds.")
    parser.add_argument('--port', type=int, default=8000, help="Web server port")
    args, _ = parser.parse_known_args()

    logger.info("Starting webserver with args: %s", args)

    backend_server(args.rate, args.channels, args.frame_duration * args.rate // 1000).run(host="0.0.0.0", port=args.port)
