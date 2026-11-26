"""자막(SRT) 만들기. 계약: 한 줄 22자 이하, 2줄 이내."""

from __future__ import annotations

from typing import List, Sequence, Tuple

MAX_LINE_CHARS = 22
MAX_LINES = 2


def wrap_caption(text: str, max_chars: int = MAX_LINE_CHARS, max_lines: int = MAX_LINES) -> str:
    """자막을 max_chars 이하 줄로 나눈다. 띄어쓰기에서 끊고, 긴 단어는 글자 수로 자른다."""
    lines: List[str] = []
    for raw_line in str(text or "").replace("\r", "").split("\n"):
        current = ""
        for word in raw_line.split():
            while len(word) > max_chars:
                if current:
                    lines.append(current)
                    current = ""
                lines.append(word[:max_chars])
                word = word[max_chars:]
            candidate = f"{current} {word}".strip()
            if len(candidate) <= max_chars:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
    if len(lines) > max_lines:
        kept = lines[:max_lines]
        last = kept[-1]
        kept[-1] = (last[: max_chars - 1] if len(last) >= max_chars else last) + "…"
        lines = kept
    return "\n".join(lines)


def srt_timestamp(seconds: float) -> str:
    """정수 밀리초로 먼저 반올림해서 x.9996초 같은 값이 1초 어긋나지 않게 한다."""
    total_ms = max(0, int(round(float(seconds) * 1000)))
    hours, rest = divmod(total_ms, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    secs, ms = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def build_srt(cues: Sequence[Tuple[float, float, str]]) -> str:
    """(시작초, 끝초, 글자) 목록 → SRT 본문. 글자가 빈 항목은 건너뛴다."""
    blocks: List[str] = []
    index = 1
    for start, end, text in cues:
        body = wrap_caption(text)
        if not body or end <= start:
            continue
        blocks.append(f"{index}\n{srt_timestamp(start)} --> {srt_timestamp(end)}\n{body}\n")
        index += 1
    return "\n".join(blocks)
