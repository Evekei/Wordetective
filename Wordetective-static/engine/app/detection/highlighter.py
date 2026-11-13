def build_highlighted_segments(original_text: str, risk_items: list[dict]) -> list[dict]:
    segments: list[dict] = []

    for item in sorted(risk_items, key=lambda risk: (risk["original_start"], risk["original_end"])):
        start = max(0, min(len(original_text), int(item["original_start"])))
        end = max(start, min(len(original_text), int(item["original_end"])))
        segments.append(
            {
                "start": start,
                "end": end,
                "text": original_text[start:end],
                "risk_type": item["risk_type"],
                "risk_level": item["risk_level"],
                "matched_by": item["matched_by"],
                "tooltip": item["description"] or f"涉及{item['risk_type']}",
            }
        )

    return segments
