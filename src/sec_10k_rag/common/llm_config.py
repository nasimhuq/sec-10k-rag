import os

from dotenv import load_dotenv
from openai import OpenAI as llm_client

from sec_10k_rag.common.config import ROOT_DIR

__all__ = ["llm_client", "LLM_API_KEY", "LLM_BASE_URL"]

load_dotenv(ROOT_DIR / ".env")
LLM_API_KEY: str = os.environ["OPEN_ROUTER_API_KEY"]
LLM_BASE_URL = "https://openrouter.ai/api/v1"


def ask_llm(
    llm: llm_client, model: str, temperature: float, system: str, user: str
) -> str:
    reply = llm.chat.completions.create(
        model=model,
        temperature=temperature,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return reply.choices[0].message.content or ""
