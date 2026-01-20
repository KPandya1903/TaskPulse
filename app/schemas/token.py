"""Token Pydantic schemas."""

from pydantic import BaseModel


class Token(BaseModel):
    """Schema for token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    """Schema for token refresh request."""

    refresh_token: str


class TokenPayload(BaseModel):
    """Schema for decoded token payload."""

    sub: str
    exp: int
    type: str
