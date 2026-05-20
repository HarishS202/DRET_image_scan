import json
import re

from huggingface_hub import InferenceClient


class LLMService:
    def __init__(self, token: str | None, model: str) -> None:
        self._client = InferenceClient(token=token)
        self._model = model

    def extract_json(self, prompt: str, fallback: dict) -> dict:
        completion = self._safe_completion(prompt)

        if not completion:
            return fallback

        if not isinstance(completion, str):
            completion = str(completion)

        cleaned = self._strip_markdown(completion)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return fallback

    def _safe_completion(self, prompt: str) -> str:
        try:
            return self._client.text_generation(
                prompt,
                model=self._model,
                max_new_tokens=1200,
                temperature=0.1,
                do_sample=False,
                return_full_text=False,
            )
        except Exception:
            # Some hosted models expose only chat completion and may raise StopIteration in text_generation.
            try:
                chat = self._client.chat_completion(
                    model=self._model,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ],
                    max_tokens=1200,
                    temperature=0.1,
                )
                if not getattr(chat, "choices", None):
                    return ""
                message = chat.choices[0].message
                return getattr(message, "content", "") or ""
            except Exception:
                return ""

    @staticmethod
    def _strip_markdown(text: str) -> str:
        text = text.strip()
        fenced = re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
        if fenced:
            return fenced[0].strip()
        return text
