import json
import re
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

REJECTION_CODE_DESCRIPTION = {
    "A": "rusty or corroded condition",
    "B": "damaged condition",
    "D": "failed return disposition rules",
    "H": "used or not in new condition",
    "I": "inspection criteria not met",
    "N": "superseded part",
    "O": "part not authorized for return",
    "R": "packaging not in salable condition",
    "S": "quality screening rejection",
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
        rejection_map = self._extract_rejection_map(rejection_text)
        rga_doc_type = self.detect_document_type(rga_text)
        rejected_doc_type = self.detect_document_type(rejection_text)

        for item in extracted.get("lines", []):
            rej = item.get("rejection", {}) or {}
            part_number = str(item.get("part_number", "") or "").strip()
            matched_rejection = rejection_map.get(part_number, {})

            code = str(rej.get("code", "") or matched_rejection.get("code", "")).upper().strip()
            comment = str(rej.get("comment", "") or matched_rejection.get("comment", "")).strip()
            reason_text = str(rej.get("reason_text", "") or "").strip()

            if code and not reason_text:
                reason_text = self._build_reason_text(code=code, comment=comment)

            mapped = DEFAULT_CODE_MAP.get(code, "")
            confidence = float(item.get("confidence", 0.0) or 0.0)
            confidence = min(max(confidence, 0.0), 1.0)

            qty_shipped = int(item.get("qty_shipped", 0) or 0)
            qty_approved = int(item.get("qty_approved", 0) or 0)
            qty_rejected = int(item.get("qty_rejected", max(qty_shipped - qty_approved, 0)) or 0)

            line = ReturnLine(
                line_number=int(item.get("line_number", 0) or 0),
                part_number=part_number,
                description=str(item.get("description", "") or "").strip(),
                qty_shipped=qty_shipped,
                qty_approved=qty_approved,
                qty_rejected=qty_rejected,
                confidence=confidence,
                auto_apply=confidence >= self.threshold,
                rejection=RejectionDetail(
                    code=code,
                    mapped_bms_code=mapped,
                    comment=comment,
                    reason_text=reason_text,
                ),
            )
            lines.append(line)

        auto_applied = sum(1 for ln in lines if ln.auto_apply)
        review_lines = len(lines) - auto_applied
        warnings = self._build_warnings(
            rga_doc_type=rga_doc_type,
            rejected_doc_type=rejected_doc_type,
            lines=lines,
            rejection_map=rejection_map,
        )

        return ProcessingResult(
            dealer_name=str(extracted.get("dealer_name", "") or "").strip(),
            rga_number=str(extracted.get("rga_number", "") or "").strip(),
            rga_document_type=rga_doc_type,
            rejected_document_type=rejected_doc_type,
            warnings=warnings,
            total_lines=len(lines),
            auto_applied_lines=auto_applied,
            review_lines=review_lines,
            estimated_minutes_saved=auto_applied * 5,
            lines=lines,
            raw_ocr_rga=rga_text,
            raw_ocr_rejections=rejection_text,
        )

    @staticmethod
    def detect_document_type(text: str) -> str:
        value = text.lower()
        if "rejected parts" in value or ("rejection" in value and "code" in value):
            return "rejection_list"
        if "credit memo" in value or "invoice" in value:
            return "credit_memo"
        if "rga" in value or "dret" in value or "ceco" in value:
            return "rga_form"
        return "unknown"

    @staticmethod
    def _extract_rejection_map(text: str) -> dict[str, dict[str, str]]:
        matches: dict[str, dict[str, str]] = {}

        patterns = [
            re.compile(
                r"\b(?P<part>\d{6,}[A-Z0-9]*)\b\s+(?P<qty>\d+)\s+(?P<code>[A-T])\b\s*(?P<comment>.*)",
                flags=re.IGNORECASE,
            ),
            re.compile(
                r"\b(?P<part>\d{6,}[A-Z0-9]*)\b\s+(?P<code>[A-T])\b\s*[-:]\s*(?P<comment>.+)",
                flags=re.IGNORECASE,
            ),
        ]

        for raw_line in text.splitlines():
            line = re.sub(r"\s+", " ", raw_line).strip()
            if not line:
                continue

            for pattern in patterns:
                m = pattern.search(line)
                if not m:
                    continue

                part = (m.groupdict().get("part") or "").strip()
                code = (m.groupdict().get("code") or "").upper().strip()
                comment = (m.groupdict().get("comment") or "").strip(" -:")

                if not part or not code:
                    continue

                matches[part] = {
                    "code": code,
                    "comment": comment,
                }
                break

        return matches

    @staticmethod
    def _build_reason_text(code: str, comment: str) -> str:
        base = REJECTION_CODE_DESCRIPTION.get(code, "inspection rejection")
        if comment:
            return f"Item rejected - {base}. Inspector notes: {comment}."
        return f"Item rejected - {base}."

    @staticmethod
    def _build_warnings(
        rga_doc_type: str,
        rejected_doc_type: str,
        lines: list[ReturnLine],
        rejection_map: dict[str, dict[str, str]],
    ) -> list[str]:
        warnings: list[str] = []

        if rga_doc_type == "unknown":
            warnings.append("First document could not be identified as an RGA form. Upload the filled RGA inspection page.")
        elif rga_doc_type == "credit_memo":
            warnings.append("First document appears to be a credit memo, not an RGA inspection form.")

        if rejected_doc_type != "rejection_list":
            warnings.append("Second document is not a rejected-parts list with code/comment entries.")

        has_any_code = any((line.rejection.code or "").strip() for line in lines)
        if lines and not has_any_code and not rejection_map:
            warnings.append("No rejection codes detected. Rejection reasons cannot be generated for this upload pair.")

        return warnings

    def heuristic_extract(self, rga_text: str, rejection_text: str) -> dict:
        merged_text = f"{rga_text}\n{rejection_text}"
        dealer_name = self._extract_dealer_name(merged_text)
        rga_number = self._extract_rga_number(merged_text)
        lines = self._extract_lines_from_text(merged_text)

        return {
            "dealer_name": dealer_name,
            "rga_number": rga_number,
            "lines": lines,
        }

    @staticmethod
    def _extract_dealer_name(text: str) -> str:
        patterns = [
            r"SOLD\s*TO\s*\n\s*([^\n]+)",
            r"SHIP\s*TO\s*\n\s*([^\n]+)",
        ]
        for pattern in patterns:
            m = re.search(pattern, text, flags=re.IGNORECASE)
            if m:
                value = m.group(1).strip()
                # OCR frequently glues SOLD TO and SHIP TO names into one line.
                split_markers = [" GPM PUMP", " PAGE ", " UNIT "]
                for marker in split_markers:
                    idx = value.upper().find(marker.strip().upper())
                    if idx > 0:
                        value = value[:idx].strip()
                        break
                return value
        return ""

    @staticmethod
    def _extract_rga_number(text: str) -> str:
        m = re.search(r"\bRTN[\w-]+\b", text, flags=re.IGNORECASE)
        return m.group(0) if m else ""

    @staticmethod
    def _extract_lines_from_text(text: str) -> list[dict]:
        rows: list[dict] = []
        line_number = 1

        seen_parts: set[str] = set()
        part_pattern = re.compile(r"\b(\d{6,}[A-Z0-9]*)\b", flags=re.IGNORECASE)

        for raw_line in text.splitlines():
            if "CECO" not in raw_line.upper():
                continue

            line = re.sub(r"\s+", " ", raw_line).strip()
            if not line:
                continue

            part_match = part_pattern.search(line)
            if not part_match:
                continue

            part_number = part_match.group(1)
            if part_number in seen_parts:
                continue

            ceco_idx = line.upper().find(" CECO")
            if ceco_idx <= part_match.end():
                continue

            prefix = line[: part_match.start()].strip()
            description = line[part_match.end() : ceco_idx].strip(" -:\u201c\u201d\u2019'\"")
            description = re.sub(r"\s+", " ", description)

            if not description:
                continue

            qty_values = [abs(int(x)) for x in re.findall(r"-\s*(\d+)|\b(\d+)\b", prefix) for x in x if x]
            if len(qty_values) >= 2:
                qty_shipped = qty_values[0]
                qty_approved = qty_values[1]
            elif len(qty_values) == 1:
                qty_shipped = qty_values[0]
                qty_approved = qty_values[0]
            else:
                qty_shipped = 1
                qty_approved = 1

            qty_approved = min(qty_approved, qty_shipped)
            qty_rejected = max(qty_shipped - qty_approved, 0)

            rows.append(
                {
                    "line_number": line_number,
                    "part_number": part_number,
                    "description": description,
                    "qty_shipped": qty_shipped,
                    "qty_approved": qty_approved,
                    "qty_rejected": qty_rejected,
                    "confidence": 0.58,
                    "rejection": {
                        "code": "",
                        "comment": "",
                        "reason_text": "",
                    },
                }
            )
            seen_parts.add(part_number)
            line_number += 1

        return rows
