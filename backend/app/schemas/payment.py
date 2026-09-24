"""Payment API schemas."""
from pydantic import BaseModel, ConfigDict, Field


class StripeStatusOut(BaseModel):
    enabled: bool


class StripeCheckoutOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    url: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
