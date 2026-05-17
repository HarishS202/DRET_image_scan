import json
from dataclasses import dataclass

from app.models import ProcessingResult, RejectionDetail, ReturnLine


# Initial lookup based on requirement deck examples; extend with full A-T mapping in production.
DEFAULT_CODE_MAP = {
    "A": "3",  # Rusty/Corroded
    "B": "5",  # Damaged
    "D": "7",
    "H": "4",  # Used / Not in New Condition
    "I": "8",
    "N": "1",  # Superseded Part
    "O": "2",  # Part Not Authorized
    "R": "6",
    "S": "9",
}


@dataclass
class InspectionEngine:
    threshold: float

    def build_prompt(self, rga_text: str, rejection_text: str) -> str:
        schema = {
            "dealer_name": "",
            "rga_number": "",
            "lines": [
                {
                    "line_number": 1,
                    "part_number": "",
                    "description": "",
                    "qty_shipped": 0,
                    "qty_approved": 0,
                    "qty_rejected": 0,
                    "confidence": 0.0,
                    "rejection": {
                        "code": "",
                        "comment": "",
                        "reason_text": "",
                    },
                }
            ],
        }

        return (
            "You are a strict JSON extraction assistant for dealer parts return inspections. "
            "Extract structured data from two OCR texts and return ONLY JSON with this schema:\n"
            f"{json.dumps(schema)}\n\n"
            "Rules:\n"
            "1) If not present, use empty string or 0.\n"
            "2) qty_rejected = max(qty_shipped - qty_approved, 0) when missing.\n"
            "3) confidence must be between 0.0 and 1.0.\n"
            "4) Keep one object per return line.\n"
            "5) reason_text must be concise and professional if a rejection code exists.\n\n"
            f"RGA OCR text:\n{rga_text}\n\n"
            f"Rejected-list OCR text:\n{rejection_text}"
        )

    def post_process(self, extracted: dict, rga_text: str, rejection_text: str) -> ProcessingResult:
        lines: list[ReturnLine] = []

        for item in extracted.get("lines", []):
            rej = item.get("rejection", {}) or {}
            code = str(rej.get("code", "")).upper().strip()
            mapped = DEFAULT_CODE_MAP.get(code, "")
            confidence = float(item.get("confidence", 0.0) or 0.0)
            confidence = min(max(confidence, 0.0), 1.0)

            qty_shipped = int(item.get("qty_shipped", 0) or 0)
            qty_approved = int(item.get("qty_approved", 0) or 0)
            qty_rejected = int(item.get("qty_rejected", max(qty_shipped - qty_approved, 0)) or 0)

            line = ReturnLine(
                line_number=int(item.get("line_number", 0) or 0),
                part_number=str(item.get("part_number", "") or "").strip(),
                description=str(item.get("description", "") or "").strip(),
                qty_shipped=qty_shipped,
                qty_approved=qty_approved,
                qty_rejected=qty_rejected,
                confidence=confidence,
                auto_apply=confidence >= self.threshold,
                rejection=RejectionDetail(
                    code=code,
                    mapped_bms_code=mapped,
                    comment=str(rej.get("comment", "") or "").strip(),
                    reason_text=str(rej.get("reason_text", "") or "").strip(),
                ),
            )
            lines.append(line)

        auto_applied = sum(1 for ln in lines if ln.auto_apply)
        review_lines = len(lines) - auto_applied

        return ProcessingResult(
            dealer_name=str(extracted.get("dealer_name", "") or "").strip(),
            rga_number=str(extracted.get("rga_number", "") or "").strip(),
            total_lines=len(lines),
            auto_applied_lines=auto_applied,
            review_lines=review_lines,
            estimated_minutes_saved=auto_applied * 5,
            lines=lines,
            raw_ocr_rga=rga_text,
            raw_ocr_rejections=rejection_text,
        )
