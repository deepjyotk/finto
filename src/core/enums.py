"""Core enums for the application."""

from enum import Enum


class LLMModel(str, Enum):
    """Supported AI models."""

    GPT4oMini = "gpt-4o-mini"
    GPT4p1 = "gpt-4.1"
