from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterIn(BaseModel):
    username: str = Field(min_length=2, max_length=40)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("username too short")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    uid: str
    username: str
    email: str
    avatar_url: str | None
    agent_count: int


class AuthConfigOut(BaseModel):
    google: bool


class AgentIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    role_behavior: str = Field(min_length=10, max_length=6000)

    @field_validator("name", "role_behavior")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class AgentOut(BaseModel):
    aid: str
    name: str
    role_behavior: str
    status: str  # free | busy (derived from live calls)
    lifecycle: str  # PENDING | ACTIVE


class PaymentIn(BaseModel):
    amount: Decimal = Field(ge=0, le=Decimal("1000000"), decimal_places=2)


class ManagerOut(BaseModel):
    mid: str
    uid: str
