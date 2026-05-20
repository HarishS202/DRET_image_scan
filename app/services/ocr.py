from io import BytesIO
import hashlib
from collections import deque
import re

from huggingface_hub import InferenceClient
from PIL import Image
import pytesseract


class OCRService:
    def __init__(self, token: str | None, model: str, mode: str = "local_first") -> None:
        self._client = InferenceClient(token=token, timeout=10)
        self._model = model
        self._mode = (mode or "local_first").strip().lower()
        self._cache: dict[str, str] = {}
        self._cache_order: deque[str] = deque()
        self._max_cache_entries = 256

    def image_to_text(self, image_bytes: bytes) -> str:
        cache_key = self._cache_key(image_bytes)
        if cache_key in self._cache:
            return self._cache[cache_key]

        if self._mode == "local_first":
            local_text = self._local_tesseract_ocr(image_bytes)
            if local_text and self._quality_score(local_text) >= 3:
                self._put_cache(cache_key, local_text)
                return local_text

        try:
            result = self._client.image_to_text(image=image_bytes, model=self._model)
            text = self._extract_generated_text(result)
            if text:
                # In local-first mode, prefer the higher-quality OCR output.
                if self._mode == "local_first":
                    local_text = self._local_tesseract_ocr(image_bytes)
                    if self._quality_score(local_text) > self._quality_score(text):
                        text = local_text
                self._put_cache(cache_key, text)
                return text
        except Exception:
            # Fall back to local OCR when hosted inference is unavailable or returns empty output.
            pass

        if self._mode != "local_first":
            text = self._local_tesseract_ocr(image_bytes)
            if text:
                self._put_cache(cache_key, text)
            return text

        return ""

    @staticmethod
    def _quality_score(text: str) -> int:
        if not text:
            return 0

        part_hits = len(re.findall(r"\b\d{6,}[A-Z0-9]*\b", text))
        ceco_hits = len(re.findall(r"\bCECO\b", text, flags=re.IGNORECASE))
        line_hits = len([line for line in text.splitlines() if line.strip()])

        return part_hits + (2 * ceco_hits) + (1 if line_hits > 8 else 0)

    @staticmethod
    def _cache_key(image_bytes: bytes) -> str:
        return hashlib.sha256(image_bytes).hexdigest()

    def _put_cache(self, key: str, value: str) -> None:
        if key in self._cache:
            self._cache[key] = value
            return

        self._cache[key] = value
        self._cache_order.append(key)

        while len(self._cache_order) > self._max_cache_entries:
            oldest = self._cache_order.popleft()
            self._cache.pop(oldest, None)

    @staticmethod
    def _extract_generated_text(result: object) -> str:
        if isinstance(result, list):
            chunks = []
            for item in result:
                if isinstance(item, dict):
                    text = item.get("generated_text", "")
                else:
                    text = getattr(item, "generated_text", "")
                if text:
                    chunks.append(text)
            return "\n".join(chunks).strip()

        if isinstance(result, dict):
            return str(result.get("generated_text", "")).strip()

        return str(getattr(result, "generated_text", "")).strip()

    @staticmethod
    def _local_tesseract_ocr(image_bytes: bytes) -> str:
        try:
            image = Image.open(BytesIO(image_bytes)).convert("L")
            # psm 6 assumes a block of text and performs better on scanned forms.
            return pytesseract.image_to_string(image, config="--psm 6").strip()
        except Exception:
            return ""
