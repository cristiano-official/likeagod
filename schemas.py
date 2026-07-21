from datetime import datetime
from typing import Any, Dict, List, Optional

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


class DuelHistoryEntry(BaseModel):
    id: int
    map_name: str
    total_bank: float
    opponent_username: str
    opponent_avatar: str
    creator_score: int
    guest_score: int
    status: str
    won: bool
    ended_at: Optional[datetime] = None
    created_at: datetime


class RecentDuelEntry(BaseModel):
    id: int
    map_name: str
    total_bank: float
    opponent_username: str
    creator_score: int
    guest_score: int
    i_am_creator: bool
    won: bool
    ended_at: Optional[datetime] = None


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
    recent_duels: Optional[List[RecentDuelEntry]] = None


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
    creator_avatar: str
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
    is_private: bool = False
    invite_token: Optional[str] = None
    # Match-orchestration fields
    game_server_id: Optional[int] = None
    connect_url: Optional[str] = None
    warmup_started_at: Optional[datetime] = None
    live_started_at: Optional[datetime] = None
    reserved_at: Optional[datetime] = None
    creator_connected: Optional[bool] = None
    guest_connected: Optional[bool] = None
    last_round_number: Optional[int] = None
    paused_by_user_id: Optional[int] = None


class DuelRoundEventResponse(BaseModel):
    id: int
    duel_id: int
    round_number: int
    creator_score: int
    guest_score: int
    payload: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


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
    private_commission_percent: float = 10.0
    authenticated: bool
    user: Optional[MainUserPayload] = None
    stats: Optional[MainStatsPayload] = None
    my_duels: List[ActiveDuelPayload]
    maintenance_mode: bool = False


# ==================== GAME SERVER SCHEMAS ====================

class GameServerCreate(BaseModel):
    label: str
    connect_url: str
    ip: str
    port: int


class GameServerUpdate(BaseModel):
    label: Optional[str] = None
    connect_url: Optional[str] = None
    ip: Optional[str] = None
    port: Optional[int] = None
    status: Optional[str] = None


class GameServerResponse(BaseModel):
    id: int
    label: Optional[str] = None
    connect_url: Optional[str] = None
    ip: Optional[str] = None
    port: Optional[int] = None
    status: str
    current_duel_id: Optional[int] = None
    last_heartbeat_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
