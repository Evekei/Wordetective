from pathlib import Path

from app.core.config import DATA_ROOT
from app.utils.file_loader import load_structured_file


TEMPLATE_PATH = DATA_ROOT / "rules" / "replacement_templates.csv"
CONSERVATIVE_FALLBACKS = {
    "绝对化用语": "当前活动优惠价格",
    "功效承诺": "坚持使用有助于改善",
    "价格宣传": "当前活动优惠价格",
    "权威背书": "相关信息请以官方说明为准",
    "收益承诺": "相关表现需结合实际情况判断",
}
MARKETING_FALLBACKS = {
    "绝对化用语": "热门优惠活动进行中",
    "功效承诺": "受到许多用户关注和好评",
    "价格宣传": "优惠活动火热进行中",
    "权威背书": "产品信息持续受到关注",
    "收益承诺": "欢迎进一步了解产品表现",
}
TEMPLATE_TYPE_MAP = {
    "绝对化用语": "absolute_terms",
    "功效承诺": "medical_claims",
    "收益承诺": "guarantee_claim",
}


def generate_rewrites(original_text: str, risk_items: list[dict]) -> dict:
    templates = _load_templates()
    conservative_text = _apply_replacements(
        original_text,
        risk_items,
        templates,
        prefer_marketing=False,
    )
    marketing_text = _apply_replacements(
        original_text,
        risk_items,
        templates,
        prefer_marketing=True,
    )
    return {
        "conservative_text": conservative_text,
        "marketing_text": marketing_text,
    }


def _apply_replacements(
    original_text: str,
    risk_items: list[dict],
    templates: dict[str, str],
    prefer_marketing: bool,
) -> str:
    rewritten = original_text
    replacements = []

    for item in risk_items:
        replacement = _choose_replacement(item, templates, prefer_marketing=prefer_marketing)
        replacements.append((int(item["original_start"]), int(item["original_end"]), replacement))

    for start, end, replacement in sorted(replacements, key=lambda value: value[0], reverse=True):
        rewritten = rewritten[:start] + replacement + rewritten[end:]

    return rewritten


def _choose_replacement(item: dict, templates: dict[str, str], prefer_marketing: bool) -> str:
    if not prefer_marketing and item.get("replacement"):
        return str(item["replacement"])

    template_key = TEMPLATE_TYPE_MAP.get(item["risk_type"])
    if template_key and template_key in templates:
        template_text = templates[template_key]
        if prefer_marketing:
            return _marketingize_template(template_text, item["risk_type"])
        return template_text

    fallback_map = MARKETING_FALLBACKS if prefer_marketing else CONSERVATIVE_FALLBACKS
    return fallback_map.get(item["risk_type"], "建议改为更审慎、可验证的表达")


def _load_templates() -> dict[str, str]:
    template_rows = load_structured_file(Path(TEMPLATE_PATH)).to_dict(orient="records")
    templates: dict[str, str] = {}
    for row in template_rows:
        risk_type = str(row.get("risk_type", "")).strip()
        template_text = str(row.get("template_text", "")).strip()
        if risk_type and template_text:
            templates[risk_type] = template_text
    return templates


def _marketingize_template(template_text: str, risk_type: str) -> str:
    marketing_overrides = {
        "绝对化用语": "热门优惠活动进行中",
        "功效承诺": "受到许多用户关注和好评",
        "收益承诺": "欢迎进一步了解产品表现",
    }
    return marketing_overrides.get(risk_type, template_text)
