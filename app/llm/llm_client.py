import os
import time
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Load provider from env
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()


# =========================
# GEMINI
# =========================
def generate_gemini(prompt: str) -> str:
    try:
        import google.generativeai as genai

        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

        model = genai.GenerativeModel("gemini-1.5-flash-latest")

        response = model.generate_content(prompt)

        return response.text

    except Exception as e:
        return f"Gemini error: {e}"


# =========================
# GROQ (FAST + FREE)
# =========================
def generate_groq(prompt: str) -> str:
    try:
        import requests
        api_key = os.getenv("GROQ_API_KEY")

        url = "https://api.groq.com/openai/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "openai/gpt-oss-20b",
            "messages": [{"role": "user", "content": prompt}]
        }

        response = requests.post(url, headers=headers, json=data)
        result = response.json()

        # DEBUG print (optional)
        # print(result)

        if "choices" not in result:
            return f"Groq API Error: {result}"

        return result["choices"][0]["message"]["content"]

    except Exception as e:
        return f"Groq error: {e}"


# =========================
# OPENAI
# =========================
def generate_openai(prompt: str) -> str:
    try:
        from openai import OpenAI

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )

        return response.choices[0].message.content

    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return f"OpenAI error: {e}"


# =========================
# OLLAMA (LOCAL)
# =========================
def generate_ollama(prompt: str) -> str:
    try:
        import requests

        model = os.getenv("OLLAMA_MODEL", "llama3:8b")

        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False
            }
        )

        return response.json()["response"]

    except Exception as e:
        logger.error(f"Ollama error: {e}")
        return f"Ollama error: {e}"


# =========================
# MAIN ROUTER
# =========================
def generate_response(prompt: str) -> str:
    """
    Unified LLM interface
    """

    logger.info(f"Using LLM provider: {LLM_PROVIDER}")

    # Retry logic (for robustness)
    for attempt in range(3):
        try:
            if LLM_PROVIDER == "gemini":
                return generate_gemini(prompt)

            elif LLM_PROVIDER == "groq":
                return generate_groq(prompt)

            elif LLM_PROVIDER == "openai":
                return generate_openai(prompt)

            elif LLM_PROVIDER == "ollama":
                return generate_ollama(prompt)

            else:
                return f"Unknown LLM_PROVIDER: {LLM_PROVIDER}"

        except Exception as e:
            if attempt < 2:
                time.sleep(2)
            else:
                return f"LLM failed after retries: {e}"