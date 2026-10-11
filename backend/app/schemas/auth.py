import re

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.schemas.user import UserResponse


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=100, examples=["Vimal S"])
    email: EmailStr = Field(examples=["vimal@example.com"])
    # bcrypt only uses the first 72 bytes, so cap the length well below that.
    password: str = Field(min_length=10, max_length=64, examples=["Str0ng!Passw0rd"])

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = " ".join(value.split())  # trim and collapse repeated spaces
        if len(value) < 2:
            raise ValueError("Name is too short")
        return value

    @model_validator(mode="after")
    def check_password_strength(self) -> "RegisterRequest":
        password = self.password
        problems = []
        if not re.search(r"[a-z]", password):
            problems.append("a lowercase letter")
        if not re.search(r"[A-Z]", password):
            problems.append("an uppercase letter")
        if not re.search(r"\d", password):
            problems.append("a number")
        if not re.search(r"[^A-Za-z0-9]", password):
            problems.append("a symbol")
        if problems:
            raise ValueError("Password must contain " + ", ".join(problems))
        if password.lower() == str(self.email).lower():
            raise ValueError("Password must not be the same as the email")
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105 – OAuth token type name, not a secret
    expires_in: int  # seconds until the access token expires
    user: UserResponse
