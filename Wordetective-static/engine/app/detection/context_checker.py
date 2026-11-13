import re


STEP_PREFIX_PATTERN = re.compile(r"^(第[一二三四五六七八九十0-9]+步|使用方法如下|操作步骤如下)")
SOFTENING_HINTS = ("可能改善", "有助于改善", "用户反馈", "体验感受")


def apply_context_rules(matches: list[dict]) -> tuple[list[dict], float]:
    adjusted_matches: list[dict] = []
    context_bonus = 0.0

    for match in matches:
        item = dict(match)
        sentence_text = item.get("sentence_text", "")

        if _is_instructional_step(sentence_text):
            item["context_multiplier"] = 0.0
            item["context_note"] = "instructional_step"
        elif _contains_softening_hint(sentence_text):
            item["context_multiplier"] = 0.6
            item["context_note"] = "softened_claim"

        base_score = _base_score(item)
        adjusted_score = round(base_score * float(item.get("context_multiplier", 1.0)), 2)
        context_bonus += adjusted_score - base_score
        adjusted_matches.append(item)

    return adjusted_matches, round(context_bonus, 2)


def _is_instructional_step(sentence_text: str) -> bool:
    return bool(STEP_PREFIX_PATTERN.search(sentence_text.strip()))


def _contains_softening_hint(sentence_text: str) -> bool:
    return any(hint in sentence_text for hint in SOFTENING_HINTS)


def _base_score(item: dict) -> float:
    risk_level = str(item.get("risk_level", "")).strip().lower()
    level_scores = {
        "low": 10.0,
        "medium": 22.0,
        "high": 35.0,
        "very_high": 50.0,
        "critical": 50.0,
        "extreme": 50.0,
        "低": 10.0,
        "中": 22.0,
        "高": 35.0,
        "极高": 50.0,
    }
    return min(50.0, level_scores.get(risk_level, 22.0) * float(item.get("weight", 1.0)))
