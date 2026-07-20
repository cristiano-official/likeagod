from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


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
    role: str
    balance: float
    frozen_balance: float
    elo: int
    rank: int
    active_invoice: Optional[dict] = None


class UserStatsResponse(BaseModel):
    duels: int
    wins: int
    kills: int
    deaths: int
    elo: int
    rank: int
    wagered_amount: float = 0.0
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


class NewsResponse(BaseModel):
    id: int
    title: str
    image_path: str
    btn_text: Optional[str] = None
    btn_url: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DuelLobbyResponse(BaseModel):
    id: int
    map_name: str
    total_bank: float
    min_rank: int
    max_rank: int
    creator_username: str
    creator_elo: int
    creator_rank: int


class DuelRequestResponse(BaseModel):
    request_id: int
    guest_id: int
    username: str
    avatar: str
    elo: int
    rank: int


class DuelDetailsResponse(BaseModel):
    id: int
    creator_id: int
    guest_id: Optional[int] = None
    creator_username: str
    creator_elo: int
    creator_rank: int
    guest_username: Optional[str] = None
    guest_elo: Optional[int] = None
    guest_rank: Optional[int] = None
    map_name: str
    total_bank: float
    creator_score: int
    guest_score: int
    status: str
    creator_share: float
    guest_share: float


class TariffResponse(BaseModel):
    id: int
    duration_months: int
    price: float
    discount_text: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PaymentMethodResponse(BaseModel):
    id: int
    name: str
    gateway_alias: str
    type: str
    commission_label: str
    commission_percent: float
    min_amount: float
    currency_code: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class PaymentHistoryEntry(BaseModel):
    id: int
    amount: float
    currency: str
    type: str
    status: str
    date: str
    address: Optional[str] = None


class MainUserPayload(BaseModel):
    id: int
    username: str
    avatar: str
    balance: float
    is_premium: bool
    premium_until: Optional[datetime] = None
    theme: int
    effects: bool
    country: str
    language: str


class MainStatsPayload(BaseModel):
    duels: int
    wins: int
    kills: int
    deaths: int
    elo_val: int
    rank: int
    winrate: float


class ActiveDuelPayload(BaseModel):
    id: int
    status: str
    total_bank: float
    creator_name: str
    guest_name: str


class MainPayloadResponse(BaseModel):
    news: List[NewsResponse]
    commission_percent: float
    authenticated: bool
    user: Optional[MainUserPayload] = None
    stats: Optional[MainStatsPayload] = None
    my_duels: List[ActiveDuelPayload]
