"""A2UI — Agent-to-User Interface event layer.

Provides structured, streaming A2UI events as an alternative to TheSys
when THESYS_ENABLED=false. Events are emitted as SSE and cover the full
LangGraph execution lifecycle without exposing raw chain-of-thought.
"""
