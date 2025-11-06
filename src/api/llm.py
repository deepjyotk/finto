"""Simple LLM query using LangChain's ChatOpenAI."""
import os
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI

# Load .env into environment (if present)
load_dotenv()


def query(question: str) -> str:
    """Send a question to the LLM and return the text response.

    Raises RuntimeError if OPENAI_API_KEY is missing or the LLM call fails.
    """
    prompt = (
        "You are a helpful assistant. Answer the following question:\n\n"
        f"{question}\n\n"
        "Answer concisely:"
    )

    # Require OPENAI_API_KEY and use LangChain's ChatOpenAI
    openai_key = os.getenv("OPENAI_API_KEY")
    # Choose a sensible default model for 2025-era OpenAI API
    openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if not openai_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Please create a .env file with OPENAI_API_KEY=<key>"
        )

    try:
        # Rely on OPENAI_API_KEY from the environment; no need to pass api_key explicitly
        llm = ChatOpenAI(model=openai_model, temperature=0)
        result = llm.invoke(prompt)
    except Exception as e:
        raise RuntimeError(f"ChatOpenAI invocation failed: {e}") from e

    # Return the AIMessage content as a plain string
    return getattr(result, "content", str(result))