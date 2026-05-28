from __future__ import annotations

import re
from pathlib import Path

from src.core.models import ParsedPaper, ParsedSection


class DocumentParseError(RuntimeError):
    pass


def build_parsed_paper(path: Path, text: str, pages: list[str] | None = None) -> ParsedPaper:
    normalized = normalize_text(text)
    if not normalized:
        raise DocumentParseError(f"parsed text is empty: {path}")

    return ParsedPaper(
        source_path=str(path),
        title=extract_title(normalized),
        abstract=extract_abstract(normalized),
        full_text=normalized,
        sections=extract_sections(normalized),
        pages=pages or [normalized],
    )


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_title(text: str) -> str:
    title_match = re.search(r"\\title\{(?P<title>[^}]+)\}", text)
    if title_match:
        return title_match.group("title").strip()
    for line in text.splitlines()[:40]:
        stripped = line.strip(" #\t")
        if stripped and not stripped.lower().startswith("abstract"):
            return stripped[:240]
    return "Untitled manuscript"


def extract_abstract(text: str) -> str:
    abstract_match = re.search(
        r"(?is)\babstract\b[:\s]*(?P<abstract>.*?)(?:\n\s*(?:\d+\.?\s+introduction|introduction|keywords)\b)",
        text,
    )
    if abstract_match:
        return abstract_match.group("abstract").strip()[:4000]
    return ""


def extract_sections(text: str) -> list[ParsedSection]:
    sections: list[ParsedSection] = []
    lines = text.splitlines()
    current_heading = "Document"
    current_start = 1
    current_lines: list[str] = []
    heading_pattern = re.compile(r"^(#{1,3}\s+.+|[0-9]+\.?\s+[A-Z][A-Za-z ].{2,80})$")

    for index, line in enumerate(lines, start=1):
        stripped = line.strip()
        if heading_pattern.match(stripped) and current_lines:
            sections.append(
                ParsedSection(
                    heading=current_heading,
                    text="\n".join(current_lines).strip(),
                    start_line=current_start,
                )
            )
            current_heading = stripped.lstrip("# ").strip()
            current_start = index
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        sections.append(
            ParsedSection(
                heading=current_heading,
                text="\n".join(current_lines).strip(),
                start_line=current_start,
            )
        )
    return sections
