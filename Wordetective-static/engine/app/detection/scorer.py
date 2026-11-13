LEVEL_BASE_SCORES = {
    "低": 10.0,
    "中": 22.0,
    "高": 35.0,
    "极高": 50.0,
}

RISK_TYPE_LABELS = {
    "absolute_terms": "绝对化用语",
    "efficacy_promise": "功效承诺",
    "medical_claims": "功效承诺",
    "authority_claim": "权威背书",
    "guarantee_claim": "收益承诺",
    "price_promotion": "价格宣传",
}


def score_matches(
    matches: list[dict],
    sentence_count: int,
    context_bonus: float = 0.0,
) -> dict:
    scored_items: list[dict] = []
    risk_counts = {"低": 0, "中": 0, "高": 0, "极高": 0}
    risk_type_distribution: dict[str, int] = {}
    sentence_heatmap = _build_empty_heatmap(sentence_count)

    keyword_score = 0.0
    regex_score = 0.0
    total_score = 0.0

    for match in matches:
        item = dict(match)
        normalized_level = normalize_risk_level(item.get("risk_level", "中"))
        explicit_score = item.get("risk_score")
        if explicit_score is None:
            base_score = LEVEL_BASE_SCORES[normalized_level]
        else:
            base_score = float(explicit_score)
        context_multiplier = float(item.get("context_multiplier", 1.0))
        score = round(min(50.0, base_score * float(item.get("weight", 1.0)) * context_multiplier), 2)

        item["risk_level"] = normalized_level
        item["score"] = score
        item["risk_type"] = _risk_type_label(str(item.get("risk_type", "unknown")))
        scored_items.append(item)

        total_score += score
        risk_counts[normalized_level] += 1
        risk_type_distribution[item["risk_type"]] = risk_type_distribution.get(item["risk_type"], 0) + 1

        matched_by = str(item.get("matched_by", ""))
        if matched_by == "regex":
            regex_score += score
        else:
            keyword_score += score

        sentence_index = int(item.get("sentence_index", 0))
        if 0 <= sentence_index < len(sentence_heatmap):
            sentence_entry = sentence_heatmap[sentence_index]
            sentence_entry["risk_score"] = round(min(100.0, sentence_entry["risk_score"] + score), 2)
            sentence_entry["hit_count"] += 1
            sentence_entry["risk_level"] = overall_risk_level(sentence_entry["risk_score"])

    final_score = round(min(100.0, total_score), 2)
    return {
        "summary": {
            "risk_score": final_score,
            "risk_level": overall_risk_level(final_score),
            "risk_counts": {level: count for level, count in risk_counts.items() if count > 0},
            "score_breakdown": {
                "keyword_score": round(keyword_score, 2),
                "regex_score": round(regex_score, 2),
                "context_bonus": round(context_bonus, 2),
                "final_score": final_score,
            },
        },
        "risk_items": scored_items,
        "risk_type_distribution": dict(sorted(risk_type_distribution.items())),
        "sentence_heatmap": sentence_heatmap,
    }


def normalize_risk_level(level: str) -> str:
    normalized = str(level).strip().lower()
    mapping = {
        "low": "低",
        "medium": "中",
        "mid": "中",
        "high": "高",
        "very_high": "极高",
        "critical": "极高",
        "extreme": "极高",
        "低": "低",
        "中": "中",
        "高": "高",
        "极高": "极高",
    }
    return mapping.get(normalized, "中")


def overall_risk_level(score: float) -> str:
    if score >= 80:
        return "极高"
    if score >= 35:
        return "高"
    if score >= 20:
        return "中"
    return "低"


def _risk_type_label(risk_type: str) -> str:
    return RISK_TYPE_LABELS.get(risk_type, risk_type)


def _build_empty_heatmap(sentence_count: int) -> list[dict]:
    return [
        {
            "sentence_index": index,
            "risk_score": 0.0,
            "risk_level": "低",
            "hit_count": 0,
        }
        for index in range(sentence_count)
    ]
