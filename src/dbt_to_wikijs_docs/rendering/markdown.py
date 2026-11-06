"""Building Markdown documents block by block."""

from collections.abc import Iterable, Sequence


class MarkdownDocument:
    """A Markdown document whose blocks are separated by one blank line."""

    def __init__(self) -> None:
        """Start an empty document."""
        self._blocks: list[str] = []

    def add(self, markdown: str) -> None:
        """Append a raw Markdown block; an empty block is ignored."""
        block = markdown.strip("\n")
        if block:
            self._blocks.append(block)

    def heading(self, text: str, level: int = 2) -> None:
        """Append a heading."""
        self.add(f"{'#' * level} {text}")

    def paragraph(self, text: str) -> None:
        """Append a paragraph."""
        self.add(text)

    def bullets(self, items: Iterable[str]) -> None:
        """Append a bulleted list."""
        self.add("\n".join(f"- {item}" for item in items))

    def code(self, language: str, source: str) -> None:
        """Append a fenced code block."""
        self.add(f"```{language}\n{source}\n```")

    def table(self, header: Sequence[str], rows: Iterable[Sequence[str]]) -> None:
        """Append a table whose cells are escaped so they cannot break the layout."""
        header_cells = (
            f" {self.escape_cell(title)} " if title else " " for title in header
        )
        lines = [
            "|" + "|".join(header_cells) + "|",
            "|" + "|".join("---" for _ in header) + "|",
        ]
        lines += [
            "| " + " | ".join(self.escape_cell(value) for value in row) + " |"
            for row in rows
        ]
        self.add("\n".join(lines))

    def render(self) -> str:
        """Return the document as Markdown text."""
        return "\n\n".join(self._blocks) + "\n"

    @staticmethod
    def escape_cell(text: str) -> str:
        """Make `text` safe inside a table cell."""
        return text.replace("|", "\\|").replace("\n", " ").strip()
