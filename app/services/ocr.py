from huggingface_hub import InferenceClient


class OCRService:
    def __init__(self, token: str | None, model: str) -> None:
        self._client = InferenceClient(token=token)
        self._model = model

    def image_to_text(self, image_bytes: bytes) -> str:
        result = self._client.image_to_text(image=image_bytes, model=self._model)

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
