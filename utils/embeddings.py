import os

from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings

load_dotenv()


def get_embedding_model():
    """OpenAI-compatible embeddings (OpenAI or OpenRouter base URL)."""
    api_key = os.getenv("OPENAI_API_KEY", "")
    base_url = os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
    model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

    if not api_key or api_key == "your_openrouter_or_openai_key_here":
        return None

    return OpenAIEmbeddings(
        model=model,
        api_key=api_key,
        base_url=base_url,
    )
