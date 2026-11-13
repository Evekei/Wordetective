from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import csv
import re
from re import Pattern

from sqlalchemy import select

from app.core.config import DATA_ROOT, get_settings
from app.db.models import ComplianceRuleRecord
import app.db.session as session_module
from app.db.session import create_session_factory
from app.detection.preprocessing import PreprocessedText, locate_sentence, preprocess_text


RULE_SOURCE = "rules.db"
FALLBACK_RULE_SOURCE = "compliance_rules.csv"
DEFAULT_RULE_PATH = DATA_ROOT / "rules" / FALLBACK_RULE_SOURCE
SUPPORTED_MARKETS = {"CN", "US"}
SEMANTIC_HINT_CONFIGS: dict[str, dict[str, object]] = {
    "US022": {
        "theme": "efficacy_claims",
        "priority": 20,
        "patterns": (
            r"\btransform(?:s|ed|ing)? your life\b",
            r"\blife[- ]changing\b",
            r"\bgame[- ]changer\b",
            r"\bmiracle(?:\s+worker)?\b",
            r"\bvisible results?\b",
        ),
    },
    "US043": {
        "theme": "efficacy_claims",
        "priority": 10,
        "patterns": (
            r"\bclinically proven\b",
            r"\bscientifically proven\b",
            r"\bproven to\b",
            r"\beffective\b",
            r"\bvisible results?\b",
            r"\banti-aging\b",
            r"\bbrighten(?:s|ed|ing)?\b",
            r"\bwhiten(?:s|ed|ing)?\b",
            r"\bfirm(?:s|ed|ing)?\b",
            r"\blift(?:s|ed|ing)?\b",
            r"\bwrinkle(?:s)?\b",
            r"\bdark spots?\b",
        ),
    },
    "US132": {
        "theme": "efficacy_claims",
        "priority": 30,
        "patterns": (
            r"\bclinically proven\b",
            r"\bscientifically proven\b",
            r"\bproven to\b",
            r"\beffective\b",
            r"\bvisible results?\b",
            r"\banti-aging\b",
            r"\bbrighten(?:s|ed|ing)?\b",
            r"\bwhiten(?:s|ed|ing)?\b",
            r"\bfirm(?:s|ed|ing)?\b",
            r"\blift(?:s|ed|ing)?\b",
            r"\bwrinkle(?:s)?\b",
            r"\bdark spots?\b",
        ),
    },
    "US194": {
        "theme": "efficacy_claims",
        "priority": 30,
        "patterns": (
            r"\bclinically proven\b",
            r"\bscientifically proven\b",
            r"\bproven to\b",
            r"\beffective\b",
            r"\bvisible results?\b",
            r"\banti-aging\b",
            r"\bbrighten(?:s|ed|ing)?\b",
            r"\bwhiten(?:s|ed|ing)?\b",
            r"\bfirm(?:s|ed|ing)?\b",
            r"\blift(?:s|ed|ing)?\b",
            r"\bwrinkle(?:s)?\b",
            r"\bdark spots?\b",
        ),
    },
    "US024": {
        "theme": "scarcity_pricing",
        "priority": 20,
        "patterns": (
            r"\blimited (?:offer|stock|time)\b",
            r"\bwhile supplies last\b",
            r"\bselling fast\b",
            r"\blast chance\b",
            r"\bhurry\b",
            r"\bbefore (?:it|they(?:'re| are)) gone\b",
            r"\bprice(?:s)? (?:go|going) up\b",
        ),
    },
    "US045": {
        "theme": "comparison_claims",
        "priority": 20,
        "patterns": (
            r"\bbest\b",
            r"#1",
            r"\bnumber one\b",
            r"\btop rated\b",
            r"\bsuperior\b",
            r"\bbetter than\b",
            r"\boutperforms?\b",
            r"\bmore effective\b",
            r"\bsafest\b",
        ),
    },
    "US046": {
        "theme": "medical_claims",
        "priority": 10,
        "patterns": (
            r"\bcure(?:s|d)?\b",
            r"\btreat(?:s|ed|ment)?\b",
            r"\bheal(?:s|ed|ing)?\b",
            r"\bprevent(?:s|ed|ing)?\b",
            r"\bregenerate(?:s|d|ing)?\b",
            r"\bstimulate(?:s|d|ing)? collagen\b",
            r"\bboost(?:s|ed|ing)? collagen\b",
            r"\bcell(?:ular)? renewal\b",
            r"\bmelanin\b",
            r"\bacne\b",
            r"\beczema\b",
            r"\bpsoriasis\b",
            r"\bdandruff\b",
            r"\bhair loss\b",
        ),
    },
    "US133": {
        "theme": "medical_claims",
        "priority": 30,
        "patterns": (
            r"\bcure(?:s|d)?\b",
            r"\btreat(?:s|ed|ment)?\b",
            r"\bheal(?:s|ed|ing)?\b",
            r"\bprevent(?:s|ed|ing)?\b",
            r"\bregenerate(?:s|d|ing)?\b",
            r"\bstimulate(?:s|d|ing)? collagen\b",
            r"\bboost(?:s|ed|ing)? collagen\b",
            r"\bcell(?:ular)? renewal\b",
            r"\bmelanin\b",
            r"\bacne\b",
            r"\beczema\b",
            r"\bpsoriasis\b",
            r"\bdandruff\b",
            r"\bhair loss\b",
        ),
    },
    "US064": {
        "theme": "otc_labeling",
        "priority": 20,
        "patterns": (
            r"\bsunscreen\b",
            r"\bspf\s*\d+\b",
            r"\banti-dandruff\b",
            r"\bdandruff\b",
            r"\bacne treatment\b",
            r"\bdrug facts\b",
            r"\bactive ingredient(?:s)?\b",
        ),
    },
    "US092": {
        "theme": "testimonial_claims",
        "priority": 20,
        "patterns": (
            r"\bbefore(?:\s+and|\s*/)\s*after\b",
            r"\btestimonial(?:s)?\b",
            r"\breviews?\b",
            r"\bthousands of shoppers\b",
            r"\bcustomer favorite\b",
            r"\bloved by\b",
            r"\b9 out of 10\b",
            r"\bresults (?:not )?typical\b",
        ),
    },
    "US096": {
        "theme": "guarantee_claims",
        "priority": 20,
        "patterns": (
            r"\bmoney[- ]back\b",
            r"\brefund\b",
            r"\bsatisfaction guarantee\b",
            r"\bguaranteed results?\b",
        ),
    },
    "US178": {
        "theme": "meta_body_image",
        "priority": 20,
        "patterns": (
            r"\bhate your\b",
            r"\bembarrassed by\b",
            r"\btoo heavy\b",
            r"\bbelly fat\b",
            r"\bugly skin\b",
        ),
    },
    "US185": {
        "theme": "meta_personal_attribute",
        "priority": 20,
        "patterns": (
            r"\bfor people with\b",
            r"\bif you suffer from\b",
            r"\bdo you have acne\b",
            r"\byour skin disorder\b",
            r"\byou have acne\b",
        ),
    },
    "US187": {
        "theme": "meta_health_data",
        "priority": 20,
        "patterns": (
            r"\bwe know you've been\b",
            r"\bbecause you care about\b",
            r"\bwe know your skin\b",
            r"\byou've been struggling with\b",
        ),
    },
    "US193": {
        "theme": "google_false_endorsement",
        "priority": 20,
        "patterns": (
            r"\bas featured by\b",
            r"\bofficial partner of\b",
            r"\bapproved by\b",
            r"\bendorsed by\b",
            r"\brecommended by the\b",
        ),
    },
    "US201": {
        "theme": "google_clickbait",
        "priority": 20,
        "patterns": (
            r"\bdoctors hate\b",
            r"\bone weird trick\b",
            r"\bsecret ingredient\b",
            r"\bshock you\b",
            r"\bshocking\b",
        ),
    },
    "US204": {
        "theme": "google_subscription_pricing",
        "priority": 20,
        "patterns": (
            r"\bfree trial\b",
            r"\bstarter kit\b",
            r"\bsubscription\b",
            r"\bauto[- ]renew\b",
            r"\bmonthly billing\b",
        ),
    },
    "CN_HINT": {
        "theme": "cn_general_compliance",
        "priority": 10,
        "patterns": (
            r"全网最低价",
            r"7天见效",
            r"100%有效",
            r"原价\d+现价\d+",
        ),
    },
    "CN057": {
        "theme": "xhs_persona_mismatch",
        "priority": 20,
        "patterns": (
            r"\u5b55\u5987.*\u8df3\u4f1e",
            r"\u5b9d\u5988.*\u8e66\u6781",
            r"\u5b66\u751f.*\u533b\u7f8e\u624b\u672f",
            r"\u533b\u751f.*\u5356\u51cf\u80a5",
        ),
    },
    "CN058": {
        "theme": "xhs_category_mismatch",
        "priority": 20,
        "patterns": (
            r"\u5c45\u5bb6\u65e5\u7528.*\u533b\u7597\u5065\u5eb7",
            r"\u6bcd\u5a74.*\u533b\u7f8e",
            r"\u5bb6\u5c45.*\u4fdd\u5065\u54c1",
            r"\u8d26\u53f7\u8ba4\u8bc1.*\u533b\u7597\u5065\u5eb7",
        ),
    },
}
PLATFORM_ALIASES = {
    "all": "all",
    "全平台": "all",
    "Amazon": "Amazon",
    "amazon": "Amazon",
    "Google": "Google",
    "google": "Google",
    "Meta": "Meta",
    "meta": "Meta",
    "\u5168\u5e73\u53f0": "\u5168\u5e73\u53f0",
    "\u5c0f\u7ea2\u4e66": "\u5c0f\u7ea2\u4e66",
    "\u6296\u97f3": "\u6296\u97f3",
    "\u5fae\u4fe1\u516c\u4f17\u53f7": "\u5fae\u4fe1\u516c\u4f17\u53f7",
    "\u516c\u4f17\u53f7": "\u5fae\u4fe1\u516c\u4f17\u53f7",
    "\u5929\u732b": "\u5929\u732b",
    "\u4eac\u4e1c": "\u4eac\u4e1c",
    "\u62fc\u591a\u591a": "\u62fc\u591a\u591a",
    "xiaohongshu": "\u5c0f\u7ea2\u4e66",
    "douyin": "\u6296\u97f3",
    "wechat": "\u5fae\u4fe1\u516c\u4f17\u53f7",
    "tmall": "\u5929\u732b",
    "jd": "\u4eac\u4e1c",
    "pinduoduo": "\u62fc\u591a\u591a",
}


@dataclass(frozen=True)
class ComplianceRule:
    rule_id: str
    match_type: str
    keyword: str
    canonical_keyword: str
    scenario_key: str
    condition_pattern: str | None
    condition_scope: str
    risk_type: str
    risk_level: str
    risk_score: float
    platform: str
    market: str
    description: str
    legal_basis: str
    replacement: str | None
    pattern: Pattern[str] | None = None


@dataclass(frozen=True)
class ComplianceRuleStore:
    buckets: dict[tuple[str, str, str], list[ComplianceRule]]
    rule_source: str

    def rules_for(self, market: str, platform: str, match_type: str) -> list[ComplianceRule]:
        normalized_market = normalize_market(market)
        if normalized_market not in SUPPORTED_MARKETS:
            return []

        normalized_platform = normalize_platform(platform)
        keys = [(normalized_market, "all", match_type)]
        if normalized_platform != "all":
            keys.append((normalized_market, normalized_platform, match_type))

        rules: list[ComplianceRule] = []
        seen_rule_ids: set[str] = set()
        for key in keys:
            for rule in self.buckets.get(key, []):
                if rule.rule_id not in seen_rule_ids:
                    rules.append(rule)
                    seen_rule_ids.add(rule.rule_id)
        return rules


def normalize_market(market: str | None) -> str:
    return str(market or "").strip().upper()


def normalize_platform(platform: str | None) -> str:
    raw = str(platform or "").strip()
    if not raw:
        return "all"
    return PLATFORM_ALIASES.get(raw, PLATFORM_ALIASES.get(raw.lower(), raw))


def clear_compliance_rule_store_cache() -> None:
    get_compliance_rule_store.cache_clear()
    _load_default_rule_store.cache_clear()


@lru_cache(maxsize=8)
def get_compliance_rule_store(rule_path: str | Path | None = None) -> ComplianceRuleStore:
    if rule_path is not None:
        return _load_rule_store_from_csv(Path(rule_path))
    return _load_default_rule_store()


@lru_cache(maxsize=1)
def _load_default_rule_store() -> ComplianceRuleStore:
    try:
        return _load_rule_store_from_db()
    except Exception:
        return _load_rule_store_from_csv(DEFAULT_RULE_PATH)


def match_keyword_rules(
    preprocessed: PreprocessedText,
    market: str,
    platform: str,
    rule_path: str | Path | None = None,
) -> tuple[list[dict], int]:
    store = get_compliance_rule_store(rule_path)
    rules = store.rules_for(market, platform, "keyword")
    matches: list[dict] = []
    haystack = preprocessed.normalized_text.casefold()

    for rule in rules:
        keyword = rule.keyword.strip()
        if not keyword:
            continue

        needle = keyword.casefold()
        search_start = 0
        while True:
            match_index = haystack.find(needle, search_start)
            if match_index == -1:
                break
            end = match_index + len(keyword)
            if _condition_matches(rule, preprocessed, match_index, end):
                matches.append(_build_match(rule, store.rule_source, preprocessed, match_index, end, keyword))
            search_start = end

    return matches, len(rules)


def match_regex_rules(
    preprocessed: PreprocessedText,
    market: str,
    platform: str,
    rule_path: str | Path | None = None,
) -> tuple[list[dict], int]:
    store = get_compliance_rule_store(rule_path)
    rules = store.rules_for(market, platform, "regex")
    matches: list[dict] = []

    for rule in rules:
        if rule.pattern is None:
            continue
        for regex_match in rule.pattern.finditer(preprocessed.normalized_text):
            start, end = regex_match.span()
            if _condition_matches(rule, preprocessed, start, end):
                matches.append(_build_match(rule, store.rule_source, preprocessed, start, end, regex_match.group(0)))

    return matches, len(rules)


def get_semantic_hints(
    text: str,
    market: str,
    platform: str,
    rule_path: str | Path | None = None,
) -> list[dict]:
    store = get_compliance_rule_store(rule_path)
    rules = store.rules_for(market, platform, "semantic_hint")
    preprocessed = preprocess_text(text)
    normalized_text = str(text or "").casefold()
    selected_rules: dict[str, tuple[int, ComplianceRule, re.Match[str] | None]] = {}

    for rule in rules:
        config = SEMANTIC_HINT_CONFIGS.get(rule.rule_id)
        if config is None:
            continue
        match = _semantic_hint_match(normalized_text, config)
        if match is None:
            continue

        theme = str(config["theme"])
        score = _semantic_hint_priority(rule, int(config["priority"]))
        current = selected_rules.get(theme)
        if current is None or score > current[0]:
            selected_rules[theme] = (score, rule, match)

    return [
        _serialize_semantic_hint(rule, store.rule_source, preprocessed, match)
        for _, rule, match in selected_rules.values()
    ]


def _load_rule_store_from_db() -> ComplianceRuleStore:
    buckets: dict[tuple[str, str, str], list[ComplianceRule]] = {}
    with session_module.RulesSessionLocal() as session:
        rows = session.scalars(
            select(ComplianceRuleRecord)
            .where(ComplianceRuleRecord.enabled.is_(True))
            .order_by(ComplianceRuleRecord.id.asc())
        ).all()
        for row in rows:
            rule = _rule_from_model(row)
            key = (rule.market, rule.platform, rule.match_type)
            buckets.setdefault(key, []).append(rule)
    return ComplianceRuleStore(buckets=buckets, rule_source=RULE_SOURCE)


def _load_rule_store_from_csv(path: Path) -> ComplianceRuleStore:
    buckets: dict[tuple[str, str, str], list[ComplianceRule]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            if not _parse_bool(row.get("enabled")):
                continue
            rule = _rule_from_row(row)
            key = (rule.market, rule.platform, rule.match_type)
            buckets.setdefault(key, []).append(rule)
    return ComplianceRuleStore(buckets=buckets, rule_source=FALLBACK_RULE_SOURCE)


def _rule_from_model(row: ComplianceRuleRecord) -> ComplianceRule:
    match_type = str(row.match_type).strip()
    keyword = str(row.keyword or "").strip()
    pattern = re.compile(keyword, re.IGNORECASE) if match_type == "regex" and keyword else None
    return ComplianceRule(
        rule_id=str(row.rule_id).strip(),
        match_type=match_type,
        keyword=keyword,
        canonical_keyword=str(row.canonical_keyword or keyword).strip(),
        scenario_key=str(row.scenario_key or "default").strip() or "default",
        condition_pattern=_nullable_text(row.condition_pattern),
        condition_scope=str(row.condition_scope or "sentence").strip() or "sentence",
        risk_type=str(row.risk_type).strip(),
        risk_level=str(row.risk_level).strip(),
        risk_score=float(row.risk_score),
        platform=normalize_platform(row.platform),
        market=normalize_market(row.market),
        description=str(row.description).strip(),
        legal_basis=str(row.legal_basis).strip(),
        replacement=_nullable_text(row.replacement),
        pattern=pattern,
    )


def _rule_from_row(row: dict[str, str]) -> ComplianceRule:
    match_type = str(row.get("match_type", "")).strip()
    keyword = str(row.get("keyword", "")).strip()
    pattern = re.compile(keyword, re.IGNORECASE) if match_type == "regex" and keyword else None
    return ComplianceRule(
        rule_id=str(row.get("rule_id", "")).strip(),
        match_type=match_type,
        keyword=keyword,
        canonical_keyword=str(row.get("canonical_keyword") or keyword).strip(),
        scenario_key=str(row.get("scenario_key") or "default").strip() or "default",
        condition_pattern=_nullable_text(row.get("condition_pattern")),
        condition_scope=str(row.get("condition_scope") or "sentence").strip() or "sentence",
        risk_type=str(row.get("risk_type", "")).strip(),
        risk_level=str(row.get("risk_level", "")).strip(),
        risk_score=_parse_float(row.get("risk_score"), default=0.0),
        platform=normalize_platform(row.get("platform")),
        market=normalize_market(row.get("market")),
        description=str(row.get("description", "")).strip(),
        legal_basis=str(row.get("legal_basis", "")).strip(),
        replacement=_nullable_text(row.get("replacement")),
        pattern=pattern,
    )


def _build_match(
    rule: ComplianceRule,
    rule_source: str,
    preprocessed: PreprocessedText,
    start: int,
    end: int,
    match_text: str,
) -> dict:
    sentence = locate_sentence(preprocessed.sentences, start, end)
    return {
        "matched_by": rule.match_type,
        "match_text": match_text,
        "start": start,
        "end": end,
        "original_start": preprocessed.char_map[start],
        "original_end": preprocessed.char_map[end - 1] + 1,
        "risk_type": rule.risk_type,
        "risk_level": rule.risk_level,
        "risk_score": rule.risk_score,
        "description": _description_with_basis(rule),
        "suggestion": rule.replacement or "建议修改后再发布",
        "replacement": rule.replacement,
        "weight": 1.0,
        "sentence_index": sentence.index if sentence else 0,
        "sentence_text": sentence.text if sentence else preprocessed.normalized_text,
        "rule_reference": f"{rule.market}/{rule.platform}: {rule.keyword}",
        "context_multiplier": 1.0,
        "rule_id": rule.rule_id,
        "rule_source": rule_source,
        "canonical_keyword": rule.canonical_keyword,
        "scenario_key": rule.scenario_key,
    }


def _description_with_basis(rule: ComplianceRule) -> str:
    if not rule.legal_basis:
        return rule.description
    return f"{rule.description} 依据：{rule.legal_basis}"


def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _parse_float(value: object, default: float) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def _nullable_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _semantic_hint_match(
    normalized_text: str,
    config: dict[str, object],
) -> re.Match[str] | None:
    patterns = config.get("patterns", ())
    for pattern in patterns:
        match = re.search(str(pattern), normalized_text, re.IGNORECASE)
        if match is not None:
            return match
    return None


def _semantic_hint_priority(rule: ComplianceRule, config_priority: int) -> int:
    platform_bonus = 1000 if rule.platform != "all" else 0
    return platform_bonus + config_priority * 10 + int(rule.risk_score)


def _serialize_semantic_hint(
    rule: ComplianceRule,
    rule_source: str,
    preprocessed: PreprocessedText,
    match: re.Match[str] | None,
) -> dict:
    matched_text = ""
    matched_sentence = ""
    if match is not None:
        start, end = match.span()
        matched_text = preprocessed.normalized_text[start:end]
        sentence = locate_sentence(preprocessed.sentences, start, end)
        matched_sentence = sentence.text if sentence else preprocessed.normalized_text

    return {
        "rule_id": rule.rule_id,
        "risk_type": rule.risk_type,
        "risk_level": rule.risk_level,
        "market": rule.market,
        "platform": rule.platform,
        "description": rule.description,
        "legal_basis": rule.legal_basis,
        "suggestion": rule.replacement or "",
        "matched_text": matched_text,
        "matched_sentence": matched_sentence,
        "rule_source": rule_source,
    }


def _condition_matches(
    rule: ComplianceRule,
    preprocessed: PreprocessedText,
    start: int,
    end: int,
) -> bool:
    if not rule.condition_pattern:
        return True

    try:
        pattern = re.compile(rule.condition_pattern, re.IGNORECASE)
    except re.error:
        return False

    if rule.condition_scope == "full_text":
        return pattern.search(preprocessed.normalized_text) is not None

    sentence = locate_sentence(preprocessed.sentences, start, end)
    sentence_text = sentence.text if sentence else preprocessed.normalized_text
    return pattern.search(sentence_text) is not None
