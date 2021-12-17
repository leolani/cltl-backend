from typing import Iterable

from cltl.backend.spi.text import TextSource, TextOutput


class ConsoleOutput(TextOutput):
    def consume(self, text: str):
        print(text)


class ConsoleSource(TextSource):
    @property
    def text(self) -> Iterable[str]:
        yield input(">")
