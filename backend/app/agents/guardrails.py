"""Agent guardrails — JSON schema validation and retry policy."""

from typing import Any

from pydantic import BaseModel, Field, ValidationError


class AgentOutputSchema(BaseModel):
    predicted_prob: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    reasoning: str = Field(max_length=4000)


def validate_agent_output(data: dict[str, Any], max_retries: int = 2) -> AgentOutputSchema:
    last_error: Exception | None = None
    for _ in range(max_retries + 1):
        try:
            return AgentOutputSchema.model_validate(data)
        except ValidationError as e:
            last_error = e
    raise last_error  # type: ignore[misc]


ALLOWED_TOOLS = frozenset({"get_odds", "get_features", "submit_order_intent"})


def sanitize_news_text(text: str, max_len: int = 2000) -> str:
    cleaned = "".join(c for c in text if c.isprintable() or c in "\n\t")
    return cleaned[:max_len]
