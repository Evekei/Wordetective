from pydantic import BaseModel, ConfigDict, Field


class DetectRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    text: str
    country: str = "中国"
    market: str = "CN"
    industry: str = "通用"
    platform: str = "全平台"
    content_type: str | None = None


class DetectApiRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: str
    text: str
    country: str = "中国"
    market: str = "CN"
    industry: str = "通用"
    platform: str = "全平台"
    content_type: str = "默认类型"
    save_history: bool = True


class RiskItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    matched_by: str
    match_text: str
    start: int
    end: int
    original_start: int
    original_end: int
    risk_type: str
    risk_level: str
    description: str
    suggestion: str
    replacement: str | None = None
    weight: float
    sentence_index: int
    sentence_text: str
    rule_reference: str
    context_multiplier: float = 1.0
    score: float = 0.0
    context_note: str | None = None
    rule_id: str
    rule_source: str


class HighlightedSegment(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    start: int
    end: int
    text: str
    risk_type: str
    risk_level: str
    matched_by: str
    tooltip: str


class RiskExplanation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    risk_text: str
    risk_type: str
    reason: str
    suggestion: str
    rule_id: str
    rule_source: str


class SemanticHint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rule_id: str
    risk_type: str
    risk_level: str
    market: str
    platform: str
    description: str
    legal_basis: str
    suggestion: str
    matched_text: str = ""
    matched_sentence: str = ""
    rule_source: str


class OptimizedVersions(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    conservative_text: str
    marketing_text: str


class BeforeAfterCompare(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    before_score: float = Field(ge=0, le=100)
    after_score: float = Field(ge=0, le=100)
    score_delta: float
    before_high_count: int
    after_high_count: int


class SentenceHeatItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sentence_index: int
    text: str
    risk_score: float = Field(ge=0, le=100)
    risk_level: str
    hit_count: int


class DetectSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    risk_score: float = Field(ge=0, le=100)
    risk_level: str
    risk_counts: dict[str, int]
    score_breakdown: dict[str, float]


class EngineMetadata(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    engine_version: str
    api_version: str = "v1"
    rules_loaded: int


class DetectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    history_id: int | None = None
    summary: DetectSummary
    risk_items: list[RiskItem]
    highlighted_segments: list[HighlightedSegment]
    risk_explanations: list[RiskExplanation]
    optimized_versions: OptimizedVersions
    before_after_compare: BeforeAfterCompare
    risk_type_distribution: dict[str, int]
    sentence_heatmap: list[SentenceHeatItem]
    semantic_hints: list[SemanticHint] = Field(default_factory=list)
    metadata: EngineMetadata
    merged_result: "DetectResponse | None" = None


DetectResponse.model_rebuild()
