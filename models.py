from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float, Text
from database import Base
from datetime import datetime


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    steam_id = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    avatar = Column(String, default='')
    bio = Column(String(150), default='')
    country = Column(String(5), default='US')
    language = Column(String(5), default='en')
    theme = Column(Integer, default=0)  # 0 - Dark, 1 - Light
    effects = Column(Boolean, default=True)
    role = Column(String, default='user')  # user, admin, judge

    is_premium = Column(Boolean, default=False)
    premium_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class UserStats(Base):
    __tablename__ = "user_stats"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    balance = Column(Float, default=0.0)
    frozen_balance = Column(Float, default=0.0)
    wagered_amount = Column(Float, default=0.0)
    elo = Column(Integer, default=1000)
    duels = Column(Integer, default=0)
    wins = Column(Integer, default=0)
    kills = Column(Integer, default=0)
    deaths = Column(Integer, default=0)


class GameServer(Base):
    """Represents a CS2 dedicated-server slot managed via dathost."""
    __tablename__ = "game_servers"

    id = Column(Integer, primary_key=True, index=True)
    label = Column(String)                        # e.g. "EU-1"
    connect_url = Column(String)                  # steam://connect/ip:port
    ip = Column(String)
    port = Column(Integer)
    status = Column(String, default="open")       # open, busy, offline
    current_duel_id = Column(Integer, ForeignKey("duels.id"), nullable=True)
    last_heartbeat_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Duel(Base):
    __tablename__ = "duels"

    id = Column(Integer, primary_key=True, index=True)
    creator_id = Column(Integer, ForeignKey("users.id"))
    guest_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    map_name = Column(String, default='aim_redline')
    total_bank = Column(Float)
    creator_share = Column(Float)
    guest_share = Column(Float)

    min_rank = Column(Integer, default=1)
    max_rank = Column(Integer, default=10)
    is_private = Column(Boolean, default=False)
    # Status lifecycle: waiting → warmup → playing ⇄ paused → completed|cancelled
    # Legacy states also supported: ready, processing, disputed
    status = Column(String, default='waiting')

    creator_score = Column(Integer, default=0)
    guest_score = Column(Integer, default=0)
    winner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    demo_url = Column(String, nullable=True)
    judge_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)

    # Match-orchestration fields (CS2 server integration)
    game_server_id = Column(Integer, ForeignKey("game_servers.id"), nullable=True)
    reserved_at = Column(DateTime, nullable=True)         # when server was reserved
    warmup_started_at = Column(DateTime, nullable=True)   # when 3-min warmup began
    live_started_at = Column(DateTime, nullable=True)     # when live play began
    paused_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    pause_started_at = Column(DateTime, nullable=True)
    creator_pause_used = Column(Boolean, default=False)
    guest_pause_used = Column(Boolean, default=False)
    last_round_number = Column(Integer, default=0)
    creator_connected = Column(Boolean, default=False)
    guest_connected = Column(Boolean, default=False)
    # Premium snapshots taken at reservation time for skin-changer access
    creator_is_premium = Column(Boolean, default=False)
    guest_is_premium = Column(Boolean, default=False)


class DuelRoundEvent(Base):
    """Per-round stats reported by the CS2 plugin during live play."""
    __tablename__ = "duel_round_events"

    id = Column(Integer, primary_key=True, index=True)
    duel_id = Column(Integer, ForeignKey("duels.id"), index=True)
    round_number = Column(Integer)
    creator_score = Column(Integer)
    guest_score = Column(Integer)
    payload = Column(Text, nullable=True)  # JSON blob for extra per-round kill/death stats
    created_at = Column(DateTime, default=datetime.utcnow)


class DuelRequest(Base):
    __tablename__ = "duel_requests"

    id = Column(Integer, primary_key=True, index=True)
    duel_id = Column(Integer, ForeignKey("duels.id"))
    guest_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String, default='pending')  # pending, accepted, declined
    created_at = Column(DateTime, default=datetime.utcnow)


class News(Base):
    __tablename__ = "news"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    image_path = Column(String)
    btn_text = Column(String, nullable=True)
    btn_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class PremiumTariff(Base):
    __tablename__ = "premium_tariffs"

    id = Column(Integer, primary_key=True, index=True)
    duration_months = Column(Integer)
    price = Column(Float)
    discount_text = Column(String, nullable=True)


class TransactionHistory(Base):
    __tablename__ = "transaction_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Float)
    currency = Column(String, default="USDT")
    type = Column(String)  # deposit, withdraw
    status = Column(String, default='pending')  # pending, completed, failed
    payment_id = Column(String, nullable=True)
    address = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class PlatformSettings(Base):
    __tablename__ = "platform_settings"

    id = Column(Integer, primary_key=True, index=True)
    commission_percent = Column(Float, default=10.0)
    maintenance_mode = Column(Boolean, default=False)


class PaymentMethod(Base):
    __tablename__ = "payment_methods"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)  # Отображаемое имя ("Telegram CryptoBot")
    gateway_alias = Column(String)  # Техническое имя ("cryptobot")
    type = Column(String)  # "deposit" или "withdraw"
    commission_label = Column(String)  # Описание комиссии ("Fee: 3%")
    commission_percent = Column(Float, default=0.0)  # Процент для накрутки сверху (для CryptoBot = 3.0)
    min_amount = Column(Float, default=5.0)
    currency_code = Column(String, default="USD")
    is_active = Column(Boolean, default=True)