from typing import Literal
from pydantic import field_validator
from app.schemas.chat import AgentRequest


class ResearchRequest(AgentRequest):
    language: Literal["en", "zh"] = "en"

    @field_validator("language", mode="before")
    @classmethod
    def default_language(cls, value):
        return "en" if value is None else value
