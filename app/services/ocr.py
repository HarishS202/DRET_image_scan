from io import BytesIO

from huggingface_hub import InferenceClient
from PIL import Image
import pytesseract


class OCRService:
    def __init__(self, token: str | None, model: str) -> None:
        self._client = InferenceClient(token=token)
        self._model = model

    def image_to_text(self, image_bytes: bytes) -> str:
        try:
            result = self._client.image_to_text(image=image_bytes, model=self._model)
            text = self._extract_generated_text(result)
            if text:
                return text
        except Exception:
            # Fall back to local OCR when hosted inference is unavailable or returns empty output.
            pass

        return self._local_tesseract_ocr(image_bytes)

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
