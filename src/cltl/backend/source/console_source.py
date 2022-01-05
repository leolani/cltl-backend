from typing import Iterable, Optional

from cltl.backend.spi.text import TextSource, TextOutput


class ConsoleOutput(TextOutput):
    def consume(self, text: str, language: Optional[str] = None):
        print(text)


class ConsoleSource(TextSource):
    @property
    def text(self) -> Iterable[str]:
        yield input(">")
