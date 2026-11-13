from pathlib import Path

from sqlalchemy.orm import Session

from app.detection.compliance_rules import (
    get_semantic_hints,
    match_keyword_rules,
    match_regex_rules,
)
from app.detection.context_checker import apply_context_rules
from app.detection.highlighter import build_highlighted_segments
from app.detection.preprocessing import preprocess_text
from app.detection.rewrite import generate_rewrites
from app.detection.scorer import normalize_risk_level, score_matches
from app.schemas.detection import (
    BeforeAfterCompare,
    DetectRequest,
    DetectResponse,
    DetectSummary,
    EngineMetadata,
    HighlightedSegment,
    OptimizedVersions,
    RiskExplanation,
    RiskItem,
    SentenceHeatItem,
)


ENGINE_VERSION = "0.1.0"


def detect_text(
    session: Session,
    request: DetectRequest,
    rule_path: str | Path | None = None,
    regex_rule_path: str | Path | None = None,
) -> DetectResponse:
    if rule_path is None and regex_rule_path is not None:
        rule_path = regex_rule_path
    base_result = _run_detection_core(session, request, rule_path=rule_path)
    rewrites = generate_rewrites(request.text, base_result["risk_items"])
    conservative_request = DetectRequest(
        text=rewrites["conservative_text"],
        market=request.market,
        industry=request.industry,
        platform=request.platform,
        content_type=request.content_type,
    )
    conservative_result = _run_detection_core(
        session,
        conservative_request,
        rule_path=rule_path,
    )

    return DetectResponse(
        summary=DetectSummary(**base_result["summary"]),
        risk_items=[RiskItem(**item) for item in base_result["risk_items"]],
        highlighted_segments=[
            HighlightedSegment(**segment)
            for segment in build_highlighted_segments(request.text, base_result["risk_items"])
        ],
        risk_explanations=[
            RiskExplanation(**explanation)
            for explanation in _build_risk_explanations(base_result["risk_items"])
        ],
        optimized_versions=OptimizedVersions(**rewrites),
        before_after_compare=BeforeAfterCompare(
            **_build_before_after_compare(base_result, conservative_result)
        ),
        risk_type_distribution=base_result["risk_type_distribution"],
        sentence_heatmap=[
            SentenceHeatItem(
                **entry,
                text=base_result["sentences"][entry["sentence_index"]]
                if entry["sentence_index"] < len(base_result["sentences"])
                else request.text,
            )
            for entry in base_result["sentence_heatmap"]
        ],
        semantic_hints=base_result["semantic_hints"],
        metadata=EngineMetadata(
            engine_version=ENGINE_VERSION,
            rules_loaded=base_result["rules_loaded"],
        ),
    )


def _run_detection_core(
    session: Session,
    request: DetectRequest,
    rule_path: str | Path | None = None,
) -> dict:
    del session
    preprocessed = preprocess_text(request.text)
    semantic_hints = get_semantic_hints(
        request.text,
        request.market,
        request.platform,
        rule_path=rule_path,
    )
    if not preprocessed.normalized_text:
        return {
            "summary": {
                "risk_score": 0.0,
                "risk_level": "低",
                "risk_counts": {},
                "score_breakdown": {
                    "keyword_score": 0.0,
                    "regex_score": 0.0,
                    "context_bonus": 0.0,
                    "final_score": 0.0,
                },
            },
            "risk_items": [],
            "risk_type_distribution": {},
            "sentence_heatmap": [],
            "sentences": [],
            "semantic_hints": semantic_hints,
            "rules_loaded": 0,
        }

    keyword_matches, keyword_rules_loaded = match_keyword_rules(
        preprocessed,
        market=request.market,
        platform=request.platform,
        rule_path=rule_path,
    )
    regex_matches, regex_rules_loaded = match_regex_rules(
        preprocessed,
        market=request.market,
        platform=request.platform,
        rule_path=rule_path,
    )
    merged_matches = merge_duplicate_risks(keyword_matches + regex_matches)
    adjusted_matches, context_bonus = apply_context_rules(merged_matches)
    scored_result = score_matches(
        adjusted_matches,
        sentence_count=len(preprocessed.sentences),
        context_bonus=context_bonus,
    )
    return {
        "summary": scored_result["summary"],
        "risk_items": scored_result["risk_items"],
        "risk_type_distribution": scored_result["risk_type_distribution"],
        "sentence_heatmap": scored_result["sentence_heatmap"],
        "sentences": [sentence.text for sentence in preprocessed.sentences],
        "semantic_hints": semantic_hints,
        "rules_loaded": keyword_rules_loaded + regex_rules_loaded,
    }


def merge_duplicate_risks(matches: list[dict]) -> list[dict]:
    merged: list[dict] = []

    for match in sorted(matches, key=lambda item: (item["start"], item["end"], item["matched_by"])):
        current = dict(match)
        duplicate_found = False

        for index, existing in enumerate(merged):
            overlap_ratio = _overlap_ratio(existing["start"], existing["end"], current["start"], current["end"])
            if overlap_ratio < 0.8:
                continue

            duplicate_found = True
            merged[index] = _merge_or_select(existing, current)
            break

        if not duplicate_found:
            merged.append(current)

    return merged


def _merge_or_select(left: dict, right: dict) -> dict:
    if left["start"] == right["start"] and left["end"] == right["end"]:
        return _merge_same_span(left, right)

    left_rank = _risk_level_rank(left["risk_level"])
    right_rank = _risk_level_rank(right["risk_level"])
    if right_rank > left_rank:
        return right
    if left_rank > right_rank:
        return left
    return left if float(left.get("weight", 1.0)) >= float(right.get("weight", 1.0)) else right


def _merge_same_span(left: dict, right: dict) -> dict:
    dominant = left if _risk_level_rank(left["risk_level"]) >= _risk_level_rank(right["risk_level"]) else right
    secondary = right if dominant is left else left

    merged = dict(dominant)
    matched_by_values = {left["matched_by"], right["matched_by"]}
    merged["matched_by"] = "+".join(sorted(matched_by_values))
    if merged["matched_by"] in {"keyword+regex", "regex+keyword"}:
        merged["matched_by"] = "keyword+regex"

    merged["rule_id"] = f"{left['rule_id']}|{right['rule_id']}"
    merged["rule_source"] = f"{left['rule_source']}+{right['rule_source']}"
    merged["context_multiplier"] = min(
        float(left.get("context_multiplier", 1.0)),
        float(right.get("context_multiplier", 1.0)),
    )
    merged["description"] = dominant["description"]
    merged["suggestion"] = dominant["suggestion"]
    merged["rule_reference"] = f"{left['rule_reference']}|{right['rule_reference']}"
    merged["replacement"] = dominant.get("replacement") or secondary.get("replacement")
    return merged


def _overlap_ratio(start_a: int, end_a: int, start_b: int, end_b: int) -> float:
    overlap = max(0, min(end_a, end_b) - max(start_a, start_b))
    if overlap == 0:
        return 0.0
    shorter_length = min(end_a - start_a, end_b - start_b)
    return overlap / shorter_length if shorter_length else 0.0


def _risk_level_rank(level: str) -> int:
    normalized = normalize_risk_level(level)
    return {"低": 1, "中": 2, "高": 3, "极高": 4}[normalized]


def _build_risk_explanations(risk_items: list[dict]) -> list[dict]:
    explanations: list[dict] = []
    for item in risk_items:
        explanations.append(
            {
                "risk_text": item["match_text"],
                "risk_type": item["risk_type"],
                "reason": item["description"],
                "suggestion": item["suggestion"] or "建议改为更审慎、可验证的表达。",
                "rule_id": item["rule_id"],
                "rule_source": item["rule_source"],
            }
        )
    return explanations


def _build_before_after_compare(before_result: dict, after_result: dict) -> dict:
    return {
        "before_score": before_result["summary"]["risk_score"],
        "after_score": after_result["summary"]["risk_score"],
        "score_delta": round(
            after_result["summary"]["risk_score"] - before_result["summary"]["risk_score"],
            2,
        ),
        "before_high_count": _count_high_risks(before_result["risk_items"]),
        "after_high_count": _count_high_risks(after_result["risk_items"]),
    }


def _count_high_risks(risk_items: list[dict]) -> int:
    return sum(1 for item in risk_items if normalize_risk_level(item["risk_level"]) in {"高", "极高"})
