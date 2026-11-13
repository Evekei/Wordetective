from dataclasses import dataclass
import re


SENTENCE_ENDINGS = "。！？!?；;"


@dataclass(frozen=True)
class SentenceSpan:
    index: int
    start: int
    end: int
    original_start: int
    original_end: int
    text: str


@dataclass(frozen=True)
class PreprocessedText:
    original_text: str
    normalized_text: str
    char_map: list[int]
    sentences: list[SentenceSpan]


def preprocess_text(text: str) -> PreprocessedText:
    normalized_text, char_map = _normalize_text_with_mapping(text)
    sentences = _split_sentences(normalized_text, char_map)
    return PreprocessedText(
        original_text=text,
        normalized_text=normalized_text,
        char_map=char_map,
        sentences=sentences,
    )


def locate_sentence(sentences: list[SentenceSpan], start: int, end: int) -> SentenceSpan | None:
    for sentence in sentences:
        if sentence.start <= start < sentence.end:
            return sentence
        if start <= sentence.start and end >= sentence.end:
            return sentence
    return None


def _normalize_text_with_mapping(text: str) -> tuple[str, list[int]]:
    cleaned_chars: list[str] = []
    char_map: list[int] = []
    previous_space = False

    for index, char in enumerate(text):
        if char.isspace():
            if cleaned_chars and not previous_space:
                cleaned_chars.append(" ")
                char_map.append(index)
                previous_space = True
            continue

        cleaned_chars.append(char)
        char_map.append(index)
        previous_space = False

    normalized_text = "".join(cleaned_chars).strip()
    if not normalized_text:
        return "", []

    leading_spaces = len("".join(cleaned_chars)) - len("".join(cleaned_chars).lstrip())
    trailing_spaces = len("".join(cleaned_chars)) - len("".join(cleaned_chars).rstrip())
    if leading_spaces or trailing_spaces:
        start = leading_spaces
        end = len(char_map) - trailing_spaces
        char_map = char_map[start:end]

    return normalized_text, char_map


def _split_sentences(text: str, char_map: list[int]) -> list[SentenceSpan]:
    if not text:
        return []

    sentences: list[SentenceSpan] = []
    start = 0
    sentence_index = 0

    for index, char in enumerate(text):
        if char not in SENTENCE_ENDINGS:
            continue
        sentence = _build_sentence(text, char_map, sentence_index, start, index + 1)
        if sentence is not None:
            sentences.append(sentence)
            sentence_index += 1
        start = index + 1

    if start < len(text):
        sentence = _build_sentence(text, char_map, sentence_index, start, len(text))
        if sentence is not None:
            sentences.append(sentence)

    return sentences


def _build_sentence(
    text: str,
    char_map: list[int],
    sentence_index: int,
    raw_start: int,
    raw_end: int,
) -> SentenceSpan | None:
    segment = text[raw_start:raw_end]
    stripped = segment.strip()
    if not stripped:
        return None

    leading_match = re.match(r"\s*", segment)
    trailing_match = re.search(r"\s*$", segment)
    leading_spaces = len(leading_match.group(0)) if leading_match else 0
    trailing_spaces = len(trailing_match.group(0)) if trailing_match else 0

    start = raw_start + leading_spaces
    end = raw_end - trailing_spaces
    return SentenceSpan(
        index=sentence_index,
        start=start,
        end=end,
        original_start=char_map[start],
        original_end=char_map[end - 1] + 1,
        text=text[start:end],
    )
