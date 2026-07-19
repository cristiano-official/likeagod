from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

# ==================== USER SCHEMAS ====================

class UserBase(BaseModel):
    id: int
    username: str
    steam_id: str
    avatar: str
    bio: str
    country: str
    language: str
    theme: int
    effects: bool
    is_premium: bool
    premium_until: Optional[datetime] = None

class UserResponse(BaseModel):
    id: int
    username: str
    steam_id: str
    avatar: str
    bio: str
    country: str
    language: str
    theme: int
    effects: bool
    is_premium: bool
    premium_until: Optional[datetime] = None
    balance: float
    frozen_balance: float
    elo: int

    class Config:
        from_attributes = True

class UserStatsResponse(BaseModel):
    duels: int
    wins: int
    kills: int
    deaths: int
    elo: int
    wagered_amount: float
    winrate: float

class ProfileResponse(BaseModel):
    id: int
    username: str
    avatar: str
    bio: str
    country: str
    language: str
    theme: int
    effects: bool
    is_premium: bool
    stats: UserStatsResponse
    is_own_profile: bool

# ==================== NEWS SCHEMAS ====================

class NewsResponse(BaseModel):
    id: int
    title: str
    image_path: str
    created_at: datetime

    class Config:
        from_attributes = True

# ==================== DUEL SCHEMAS ====================

class DuelLobbyResponse(BaseModel):
    id: int
    creator_username: str
    creator_elo: int
    total_bank: float
    min_rank: int
    max_rank: int

class DuelRequestResponse(BaseModel):
    request_id: int
    guest_id: int
    username: str
    avatar: str
    elo: int

class TariffResponse(BaseModel):
    id: int
    duration_months: int
    price: float
    discount_text: Optional[str] = None