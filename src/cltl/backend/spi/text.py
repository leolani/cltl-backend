from typing import Iterable, Optional


class TextOutput:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def consume(self, text: str, language: Optional[str] = None):
        raise NotImplementedError()

    def consume_stream(self, texts: Iterable[str], language: Optional[str] = None):
        for text in texts:
            self.consume(text)


class TextSource:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def __iter__(self):
        return iter(self.text)

    @property
    def text(self) -> Iterable[str]:
        raise NotImplementedError()

    @property
    def language(self) -> Optional[str]:
        return None
