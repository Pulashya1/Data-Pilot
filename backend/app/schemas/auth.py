"""Pydantic schemas for the auth API (MASTER_PROMPT.md §9, §12 Phase 8).

A hand-rolled email regex, not `pydantic.EmailStr`, since that needs the `email-validator`
extra — not in MASTER_PROMPT.md §2's dependency list, and not worth a new dependency for a
single-field format check (§13: ask before adding a library outside the spec).
"""

import re

from pydantic import BaseModel, field_validator

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RequestLinkRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not _EMAIL_RE.match(value):
            raise ValueError("Enter a valid email address.")
        return value


class RequestLinkResponse(BaseModel):
    detail: str
    # Set only when `Settings.smtp_host` is empty (local-dev default) — see app/api/auth.py.
    dev_login_url: str | None = None


class UserOut(BaseModel):
    id: str
    email: str

    model_config = {"from_attributes": True}
