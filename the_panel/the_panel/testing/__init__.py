"""Offline test doubles: a fake Messages client and a schema-driven example builder."""
from .examples import build_example
from .fake_llm import FakeLLM, FakeParsedMessage

__all__ = ["FakeLLM", "FakeParsedMessage", "build_example"]
