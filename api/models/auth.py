"""
api/models/auth.py
──────────────────
Pydantic request/response models for authentication management endpoints.
"""

from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field


class RegisterPreflightRequest(BaseModel):
    email: str
    password: str


class RegisterPreflightResponse(BaseModel):
    ok: bool
    message: str
    email: str
    providers: List[str] = Field(default_factory=list)


class LoginPreflightRequest(BaseModel):
    email: str


class LoginPreflightResponse(BaseModel):
    ok: bool
    message: str
    email: str
    providers: List[str] = Field(default_factory=list)
    locked_until: Optional[str] = None


class LoginAuditRequest(BaseModel):
    email: str
    success: bool
    provider: str = "password"
    failure_reason: Optional[str] = None
    session_id: Optional[str] = None
    remember_me: Optional[bool] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LogoutAuditRequest(BaseModel):
    email: Optional[str] = None
    session_id: Optional[str] = None
    all_devices: bool = False


class PasswordResetAuditRequest(BaseModel):
    email: str


class PasswordResetCompleteAuditRequest(BaseModel):
    email: Optional[str] = None
    success: bool = True


class OAuthLinkRequest(BaseModel):
    provider: Optional[str] = None


class SessionHistoryItem(BaseModel):
    id: str
    provider: str
    success: bool
    login_at: Optional[str] = None
    logout_at: Optional[str] = None
    browser: Optional[str] = None
    os: Optional[str] = None
    device: Optional[str] = None
    ip_address: Optional[str] = None


class SessionHistoryResponse(BaseModel):
    sessions: List[SessionHistoryItem] = Field(default_factory=list)


class GenericAuthResponse(BaseModel):
    ok: bool = True
    message: str
