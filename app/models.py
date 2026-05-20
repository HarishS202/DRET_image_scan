from pydantic import BaseModel, Field


class RejectionDetail(BaseModel):
    code: str = Field(default="", description="Inspector code A-T")
    mapped_bms_code: str = Field(default="", description="Mapped BMS rejection code")
    comment: str = Field(default="", description="Inspector free-text comment")
    reason_text: str = Field(default="", description="Generated standardized rejection reason")


class ReturnLine(BaseModel):
    line_number: int = Field(default=0)
    part_number: str = ""
    description: str = ""
    qty_shipped: int = 0
    qty_approved: int = 0
    qty_rejected: int = 0
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    auto_apply: bool = False
    rejection: RejectionDetail = Field(default_factory=RejectionDetail)


class ProcessingResult(BaseModel):
    dealer_name: str = ""
    rga_number: str = ""
    rga_document_type: str = "unknown"
    rejected_document_type: str = "unknown"
    total_lines: int = 0
    auto_applied_lines: int = 0
    review_lines: int = 0
    estimated_minutes_saved: int = 0
    lines: list[ReturnLine] = Field(default_factory=list)
    raw_ocr_rga: str = ""
    raw_ocr_rejections: str = ""


class AnalysisSummary(BaseModel):
    current_state: list[str]
    future_state: list[str]
    phased_rollout: list[str]
    approvals_needed: list[str]
