from pydantic import BaseModel, field_validator


class AgentRequest(BaseModel):
    question: str

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        # Match Java String.length()/@Size, including supplementary characters.
        if not value.strip() or len(value.encode("utf-16-le")) // 2 > 4000:
            raise ValueError("Question must be non-blank and at most 4000 UTF-16 code units")
        return value


class AgentResponse(BaseModel):
    answer: str
    sources: list[str]
