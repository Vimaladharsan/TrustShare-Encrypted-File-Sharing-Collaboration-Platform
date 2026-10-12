from typing import Literal

from pydantic import BaseModel, Field


class MfaStatusResponse(BaseModel):
    enabled: bool
    backup_codes_remaining: int


class MfaSetupResponse(BaseModel):
    secret: str  # for typing into the app manually if the QR code can't be scanned
    otpauth_uri: str  # the standard link encoded in the QR code
    qr_code: str  # "data:image/svg+xml;base64,..." – shown directly as an <img>
    expires_in: int  # seconds to confirm before the setup is discarded


class MfaCodeRequest(BaseModel):
    # 6 digits from the authenticator app, or a backup code like "k7m2-9xqp".
    code: str = Field(min_length=6, max_length=20, examples=["123456"])


class MfaEnableResponse(BaseModel):
    backup_codes: list[str]  # shown ONCE – the user must save them somewhere safe


class MfaDisableRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)
    code: str = Field(min_length=6, max_length=20)


class MfaRequiredResponse(BaseModel):
    """Returned by /login instead of tokens when the account has MFA enabled."""

    mfa_required: Literal[True] = True
    challenge_id: str
    expires_in: int


class MfaVerifyRequest(BaseModel):
    challenge_id: str = Field(min_length=10, max_length=100)
    code: str = Field(min_length=6, max_length=20, examples=["123456"])
