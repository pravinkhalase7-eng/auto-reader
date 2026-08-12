"""Word / sentence / paragraph segmentation with stable UUID assignment."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field


SENTENCE_SPLIT = re.compile(r"(?<=[.!?।])\s+")
WORD_SPLIT = re.compile(r"\s+")


@dataclass
class WordNode:
    id: str
    text: str
    index: int
    position: int


@dataclass
class SentenceNode:
    id: str
    text: str
    position: int
    words: list[WordNode] = field(default_factory=list)


@dataclass
class ParagraphNode:
    id: str
    text: str
    position: int
    sentences: list[SentenceNode] = field(default_factory=list)


@dataclass
class SectionNode:
    id: str
    heading: str | None
    position: int
    paragraphs: list[ParagraphNode] = field(default_factory=list)


@dataclass
class ContentTree:
    title: str
    language: str
    content_type: str
    summary: str
    sections: list[SectionNode]
    full_text: str
    word_count: int


def _uid() -> str:
    return str(uuid.uuid4())


def tokenize_words(text: str) -> list[str]:
    return [w for w in WORD_SPLIT.split(text.strip()) if w]


def split_sentences(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    parts = SENTENCE_SPLIT.split(text)
    return [p.strip() for p in parts if p.strip()]


def build_paragraph(text: str, position: int, word_index_start: int = 0) -> tuple[ParagraphNode, int]:
    para = ParagraphNode(id=_uid(), text=text.strip(), position=position)
    idx = word_index_start
    for s_pos, sentence_text in enumerate(split_sentences(text)):
        sentence = SentenceNode(id=_uid(), text=sentence_text, position=s_pos)
        for w_pos, word in enumerate(tokenize_words(sentence_text)):
            sentence.words.append(WordNode(id=_uid(), text=word, index=idx, position=w_pos))
            idx += 1
        para.sentences.append(sentence)
    return para, idx


def reconstruct_from_text(
    text: str,
    *,
    title: str | None = None,
    language: str = "en",
    content_type: str = "other",
    summary: str = "",
) -> ContentTree:
    """Preserve paragraphs and poetry line breaks; do not blindly concatenate."""
    cleaned = text.replace("\r\n", "\n").strip()
    blocks = re.split(r"\n\s*\n", cleaned) if cleaned else []

    sections: list[SectionNode] = []
    current = SectionNode(id=_uid(), heading=None, position=0)
    word_index = 0
    para_pos = 0

    for block in blocks:
        lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
        if not lines:
            continue

        # Treat short single-line ALLCAPS / Title-like as heading
        if len(lines) == 1 and len(lines[0]) < 80 and not lines[0].endswith((".", "।", "?", "!")):
            if current.paragraphs:
                sections.append(current)
                current = SectionNode(id=_uid(), heading=lines[0], position=len(sections))
                para_pos = 0
            else:
                current.heading = lines[0]
            continue

        # Poetry: many short lines → keep line breaks as separate paragraphs
        if len(lines) >= 3 and all(len(ln) < 60 for ln in lines):
            for ln in lines:
                para, word_index = build_paragraph(ln, para_pos, word_index)
                current.paragraphs.append(para)
                para_pos += 1
            continue

        para_text = " ".join(lines)
        para, word_index = build_paragraph(para_text, para_pos, word_index)
        current.paragraphs.append(para)
        para_pos += 1

    if current.paragraphs or current.heading:
        sections.append(current)

    if not sections:
        sections = [SectionNode(id=_uid(), heading=None, position=0, paragraphs=[])]

    derived_title = title or (sections[0].heading if sections and sections[0].heading else "Your Lesson")
    return ContentTree(
        title=derived_title,
        language=language,
        content_type=content_type,
        summary=summary,
        sections=sections,
        full_text=cleaned,
        word_count=word_index,
    )


def flatten_words(tree: ContentTree) -> list[WordNode]:
    words: list[WordNode] = []
    for section in tree.sections:
        for para in section.paragraphs:
            for sentence in para.sentences:
                words.extend(sentence.words)
    return words
