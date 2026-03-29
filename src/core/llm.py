from html import unescape
from typing import Callable

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from src.core.enums import LLMModel, ThesysModel
from src.core.settings import thesys_settings

LLMFactory = Callable[[LLMModel | ThesysModel], BaseChatModel]


class ThesysChatOpenAI(ChatOpenAI):
    def __init__(self):
        super().__init__(
            model=thesys_settings.thesys_model,
            api_key=thesys_settings.thesys_api_key,
            base_url=thesys_settings.thesys_base_url,
        )


def _strip_thesys_wrapping(text: str | None) -> str:
    """
    Remove the Thesys `<content ...>` wrapper and HTML escaping.

    Thesys sometimes returns content wrapped in a custom <content> tag and
    HTML-encoded. This helper normalizes that to a plain string so the rest
    of the pipeline can work with raw user text.
    """
    if text is None:
        return ""

    cleaned = unescape(str(text)).strip()

    if cleaned.startswith("<content") and "</content>" in cleaned:
        try:
            first_gt = cleaned.index(">")
            last_close = cleaned.rindex("</content>")
            cleaned = cleaned[first_gt + 1 : last_close].strip()
        except ValueError:
            # Malformed wrapper; return the unescaped text
            pass

    return cleaned
