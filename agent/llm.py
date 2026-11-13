import requests

import config

OLLAMA_ERROR = (
    "Ollama'dan cevap alınamadı. Ollama'nın çalıştığını ve modelin kurulu "
    "olduğunu kontrol edin."
)


def ask_llm(prompt: str) -> str:
    try:
        response = requests.post(
            f"{config.OLLAMA_URL.rstrip('/')}/api/generate",
            json={
                "model": config.OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
            },
            timeout=(5, 120),
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return OLLAMA_ERROR

    answer = payload.get("response") if isinstance(payload, dict) else None
    return answer.strip() if isinstance(answer, str) and answer.strip() else OLLAMA_ERROR
