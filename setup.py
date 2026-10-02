from setuptools import setup, find_namespace_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

with open("VERSION", "r") as fh:
    version = fh.read().strip()

setup(
    name='cltl_backend',
    version=version,
    package_dir={'': 'src'},
    packages=find_namespace_packages(include=['cltl.*', 'cltl_service.*'], where='src'),
    data_files=[('VERSION', ['VERSION'])],
    url="https://github.com/leolani/cltl-backend",
    license='MIT License',
    author='CLTL',
    author_email='t.baier@vu.nl',
    description='Backend for Leolani',
    long_description=long_description,
    long_description_content_type="text/markdown",
    python_requires='>=3.7',
    install_requires=['numpy'],
    extras_require={
        # `requests` only, for `cltl.backend.impl.remote_storage`. `mock` and
        # `parameterized` were here and are gone: they are test libraries, nothing
        # under src/ imports either, and tests get them from
        # cltl-requirements/requirements.test.txt. A runtime extra naming them
        # made this extra uninstallable wherever they are absent -- it is what
        # broke the cltl-monitoring image, which depends on `cltl.backend[impl]`
        # to reach `requests` and installs offline with
        # `--no-index --find-links=/leolani`.
        "impl": [
            "requests"
        ],
        "local": [
            "gTTS",
            "playsound",
            'pyobjc;platform_system=="darwin"'
        ],
        "remote": [
            "gTTS",
            "pydub",
        ],
        "host": [
            "emissor",
            "cachetools",
            "pyaudio",
            "opencv-python",
            "flask<2.3"
        ],
        "service": [
            "cltl.combot",
            "emissor",
            "flask<2.3",
            "pyaudio",
            "requests",
            "soundfile",
        ],
        # `service` without the hardware. Containerised, this component only ever
        # processes audio and images that arrived over HTTP: the microphone and
        # camera are a `ClientAudioSource`/`ClientImageSource` pair that GET from
        # a device host, and the wire format is base64 ndarray JSON rather than an
        # image or audio codec. PyAudio is the one entry in `service` that is not
        # used on that path -- nothing under `cltl_service/` imports it, and the
        # two modules that do (`cltl.backend.server` and
        # `cltl.backend.source.pyaudio_source`) are reached only when
        # `run_server: True` asks for a real device, and import it inside a `try`.
        #
        # Leaving it in would mean compiling it from source in the image: there is
        # no aarch64 wheel, so it needs portaudio19-dev and a toolchain, which is
        # most of what separates cltl-base-slim from the 4 GB full base.
        "docker": [
            "cltl.combot",
            "emissor",
            "flask<2.3",
            "requests",
            "soundfile",
        ]
    },
    entry_points={
        'console_scripts': ['leoserv = cltl.backend.server:main']
    }
)
