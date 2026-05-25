"""Pydantic request/response models for the API."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


# ---- Accounts (rags) -----------------------------------------------------
class AccountIn(BaseModel):
    label: str = Field(..., min_length=1, max_length=80)
    niche: str = "quotes"          # quotes | news | both
    ig_business_id: str = ""
    ig_access_token: str = ""
    is_active: bool = True


class AccountUpdate(BaseModel):
    label: Optional[str] = None
    niche: Optional[str] = None
    ig_business_id: Optional[str] = None
    ig_access_token: Optional[str] = None
    is_active: Optional[bool] = None


# ---- Settings (rags) -----------------------------------------------------
class SettingsIn(BaseModel):
    news_api_key: Optional[str] = None
    github_username: Optional[str] = None
    github_repo: Optional[str] = None
    github_branch: Optional[str] = None
    posts_per_batch: Optional[int] = Field(None, ge=1, le=6)
    slides_per_post: Optional[int] = Field(None, ge=1, le=6)
    fixed_hashtags: Optional[str] = None


# ---- Generation ----------------------------------------------------------
class GenerateRequest(BaseModel):
    niche: str = "quotes"                      # quotes | news
    posts: Optional[int] = Field(None, ge=1, le=6)
    slides: Optional[int] = Field(None, ge=1, le=6)
    topic: Optional[str] = None                # quotes theme or news topic


class PublishRequest(BaseModel):
    batch_id: str
    post_index: int = Field(..., ge=0)
    account_id: int
