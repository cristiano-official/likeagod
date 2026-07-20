import os
import requests
import jwt
import random
import hashlib
import httpx
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from pysteamsignin.steamsignin import SteamSignIn
from dotenv import load_dotenv

from models import User, UserStats, Duel, Base, News, DuelRequest, PremiumTariff, TransactionHistory, PlatformSettings, \
    PaymentMethod
from database import engine, session_local
from schemas import (
    DuelDetailsResponse,
    DuelLobbyResponse,
    DuelRequestResponse,
    MainPayloadResponse,
    NewsResponse,
    PaymentHistoryEntry,
    PaymentMethodResponse,
    ProfileResponse,
    TariffResponse,
    UserResponse,
)

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="LikeGod Esports Tournament Platform Core API",
    description="Backend engine for competitive esports matchmaking, player statistics tracking and platform events allocation.",
    version="1.9.7",
    docs_url="/docs"
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://likeagod.net", "http://localhost", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

steam_login = SteamSignIn()
SECRET_KEY = os.getenv('SECRET_KEY', '0eb484ec834db43b23888c5f5be01103680db120b491af1379c1f30dc1f0d211')
ALGORITHM = "HS256"
STEAM_API_KEY = os.getenv('STEAM_API_KEY', '')
SERVER_API_KEY = os.getenv('SERVER_API_KEY', 'super_secret_token_for_cs2_server')

CRYPTO_PAY_TOKEN = os.getenv("CRYPTO_PAY_TOKEN", "123456:AA....")
CRYPTO_PAY_API_URL = "https://pay.crypt.bot/api"

AAIO_MERCHANT_ID = os.getenv("AAIO_MERCHANT_ID", "your_merchant_id")
AAIO_SECRET_1 = os.getenv("AAIO_SECRET_1", "your_secret_1")
AAIO_SECRET_2 = os.getenv("AAIO_SECRET_2", "your_secret_2")

Base.metadata.create_all(bind=engine)

db = session_local()
try:
    if not db.query(PlatformSettings).first():
        db.add(PlatformSettings(commission_percent=10.0))
        db.commit()

    if not db.query(PaymentMethod).first():
        db.add_all([
            PaymentMethod(name="Telegram CryptoBot", gateway_alias="cryptobot", type="deposit",
                          commission_label="Fee: 3%", commission_percent=3.0, min_amount=1.0, currency_code="USD",
                          is_active=True),
            PaymentMethod(name="Crypto Wallet Payout", gateway_alias="cryptobot", type="withdraw",
                          commission_label="Fee: 1.5%", commission_percent=0.0, min_amount=1.0, currency_code="USD",
                          is_active=True),
            PaymentMethod(name="Visa / Mastercard / СБП", gateway_alias="aaio_rub", type="deposit",
                          commission_label="Fee: 0%", commission_percent=0.0, min_amount=1.0, currency_code="RUB",
                          is_active=True)
        ])
        db.commit()
finally:
    db.close()


# ==================== UTILS & CORE MIDDLEWARES ====================

def get_db():
    db = session_local()
    try:
        yield db
    finally:
        db.close()


def decode_jwt_token(token: str) -> Optional[int]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get('user_id')
    except:
        return None


def get_current_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    token = request.cookies.get('access_token')
    if not token:
        return None
    user_id = decode_jwt_token(token)
    return db.query(User).filter(User.id == user_id).first()


def require_auth(current_user: User = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication missing or expired")
    return current_user


def require_admin(current_user: User = Depends(require_auth)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required")
    return current_user


def calculate_shares(creator_elo: int, opponent_elo: int, total_bank: float):
    weight_creator = 10 ** (creator_elo / 400)
    weight_opponent = 10 ** (opponent_elo / 400)
    chance_creator = weight_creator / (weight_creator + weight_opponent)
    return round(total_bank * chance_creator, 2), round(total_bank * (1 - chance_creator), 2)


def check_wager_limit(wagered: float, required_share: float):
    if wagered < 6.0 and required_share > 2.0:
        raise HTTPException(status_code=400, detail="Bet limit capped at $2.00 until overall wager reaches $6.00")
    elif wagered < 20.0 and required_share > 4.0:
        raise HTTPException(status_code=400, detail="Bet limit capped at $4.00 until overall wager reaches $20.00")


def check_active_match_existence(user_id: int, db: Session):
    match = db.query(Duel).filter(
        ((Duel.creator_id == user_id) | (Duel.guest_id == user_id)),
        Duel.status.in_(['waiting', 'ready', 'playing', 'processing', 'disputed'])
    ).first()
    if match:
        raise HTTPException(status_code=400, detail=f"Action blocked: You are already in an active match #{match.id}")


def get_current_commission(db: Session) -> float:
    settings = db.query(PlatformSettings).first()
    return settings.commission_percent if settings else 10.0


def get_rank_from_elo(elo: int) -> int:
    return max(1, min(10, (elo - 700) // 100))


def get_user_stats_or_404(user_id: int, db: Session) -> UserStats:
    stats = db.query(UserStats).filter(UserStats.user_id == user_id).first()
    if not stats:
        raise HTTPException(status_code=404, detail="Player statistics not found")
    return stats


def get_duel_or_404(duel_id: int, db: Session) -> Duel:
    duel = db.query(Duel).filter(Duel.id == duel_id).first()
    if not duel:
        raise HTTPException(status_code=404, detail="Duel not found")
    return duel


def serialize_duel(duel: Duel, db: Session) -> dict:
    creator = db.query(User).filter(User.id == duel.creator_id).first()
    creator_stats = get_user_stats_or_404(duel.creator_id, db)
    guest = db.query(User).filter(User.id == duel.guest_id).first() if duel.guest_id else None
    guest_stats = get_user_stats_or_404(duel.guest_id, db) if duel.guest_id else None
    return {
        "id": duel.id,
        "creator_id": duel.creator_id,
        "guest_id": duel.guest_id,
        "creator_username": creator.username if creator else "Unknown",
        "creator_elo": creator_stats.elo,
        "creator_rank": get_rank_from_elo(creator_stats.elo),
        "guest_username": guest.username if guest else None,
        "guest_elo": guest_stats.elo if guest_stats else None,
        "guest_rank": get_rank_from_elo(guest_stats.elo) if guest_stats else None,
        "map_name": duel.map_name,
        "total_bank": duel.total_bank,
        "creator_score": duel.creator_score,
        "guest_score": duel.guest_score,
        "status": duel.status,
        "creator_share": duel.creator_share,
        "guest_share": duel.guest_share,
    }


def find_user_by_target(target: str, db: Session) -> User:
    user = db.query(User).filter((User.username == target) | (User.steam_id == target)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# ==================== REST API ENDPOINTS ====================

@app.get("/auth/steam", tags=["Auth"])
async def auth_steam():
    return_to = 'https://likeagod.net/auth/steam/callback'
    return RedirectResponse(f"https://steamcommunity.com/openid/login?{steam_login.ConstructURL(return_to)}")


@app.get("/auth/steam/callback", tags=["Auth"])
async def auth_steam_callback(request: Request, db: Session = Depends(get_db)):
    steam_id = steam_login.ValidateResults(dict(request.query_params))
    if not steam_id: raise HTTPException(status_code=403, detail="Invalid Steam OpenID response")

    db_user = db.query(User).filter(User.steam_id == str(steam_id)).first()
    if not db_user:
        url = f"http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key={STEAM_API_KEY}&steamids={steam_id}"
        avatar_url = ""
        try:
            r = requests.get(url, timeout=5).json()
            avatar_url = r['response']['players'][0]['avatarfull']
        except:
            pass

        db_user = User(steam_id=str(steam_id), username=f"User_{random.randint(1000, 999999)}", avatar=avatar_url)
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        db.add(UserStats(user_id=db_user.id))
        db.commit()

    response = RedirectResponse(url="/main")
    response.set_cookie("access_token",
                        jwt.encode({'user_id': db_user.id, 'exp': datetime.utcnow() + timedelta(days=7)}, SECRET_KEY,
                                   algorithm=ALGORITHM), httponly=True, secure=True, samesite='lax',
                        domain='likeagod.net')
    return response


@app.get("/auth/logout", tags=["Auth"])
async def logout():
    response = RedirectResponse(url="/main")
    response.delete_cookie("access_token", domain='likeagod.net')
    return response


@app.get("/user/me", response_model=UserResponse, tags=["User Profile"])
async def get_my_info(current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    st = get_user_stats_or_404(current_user.id, db)

    active_tx = db.query(TransactionHistory).filter(
        TransactionHistory.user_id == current_user.id,
        TransactionHistory.type == "deposit",
        TransactionHistory.status == "pending"
    ).first()

    active_invoice_payload = None
    if active_tx:
        active_invoice_payload = {
            "amount": active_tx.amount,
            "currency": active_tx.currency,
            "pay_url": active_tx.address
        }

    return {
        "id": current_user.id, "username": current_user.username, "steam_id": current_user.steam_id,
        "avatar": current_user.avatar, "bio": current_user.bio, "country": current_user.country,
        "language": current_user.language, "theme": current_user.theme, "effects": current_user.effects,
        "is_premium": current_user.is_premium, "premium_until": current_user.premium_until, "role": current_user.role,
        "balance": st.balance, "frozen_balance": st.frozen_balance, "elo": st.elo,
        "rank": get_rank_from_elo(st.elo),
        "active_invoice": active_invoice_payload
    }


@app.post("/user/update", tags=["User Profile"])
async def update_profile(data: dict, current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    if data.get('username'):
        name = data.get('username')
        if len(name) < 3 or not name.isalnum(): raise HTTPException(status_code=400,
                                                                    detail="Invalid alphanumeric username")
        if db.query(User).filter(User.username == name, User.id != current_user.id).first(): raise HTTPException(
            status_code=409, detail="Username occupied")
        current_user.username = name
    current_user.bio = str(data.get('bio', current_user.bio))[:150]
    current_user.country = str(data.get('country', current_user.country))[:5].upper()
    if data.get('language') in ['en', 'ru', 'es', 'zh', 'de']: current_user.language = data.get('language')
    if data.get('theme') is not None: current_user.theme = int(data.get('theme'))
    if data.get('effects') is not None: current_user.effects = bool(data.get('effects'))
    db.commit()
    return {"status": "success"}


@app.get("/user/by-name/{username}", response_model=ProfileResponse, tags=["User Profile"])
async def get_public_profile(username: str, request: Request, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.username == username).first()
    if not u: raise HTTPException(status_code=404, detail="Profile not found")
    st = get_user_stats_or_404(u.id, db)
    curr = get_current_user(request, db)
    return {
        "id": u.id, "username": u.username, "avatar": u.avatar, "bio": u.bio, "country": u.country,
        "language": u.language, "theme": u.theme, "effects": u.effects,
        "is_premium": u.is_premium,
        "stats": {"duels": st.duels, "wins": st.wins, "kills": st.kills, "deaths": st.deaths, "elo": st.elo,
                  "rank": get_rank_from_elo(st.elo), "wagered_amount": st.wagered_amount,
                  "winrate": round((st.wins / st.duels * 100) if st.duels > 0 else 0, 1)},
        "is_own_profile": bool(curr and curr.id == u.id)
    }


@app.post("/api/v1/duels", tags=["Matchmaking"])
async def create_duel(data: dict, current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    check_active_match_existence(current_user.id, db)
    st = db.query(UserStats).filter(UserStats.user_id == current_user.id).first()
    bank = float(data.get('total_bank', 0))
    if bank <= 0: raise HTTPException(status_code=400, detail="Invalid prize bank")

    max_c_share, _ = calculate_shares(st.elo, 700 + (int(data.get('min_rank', 1)) * 100), bank)
    if not bool(data.get('is_private')): check_wager_limit(st.wagered_amount, max_c_share)
    if st.balance < max_c_share: raise HTTPException(status_code=400, detail="Insufficient margin balance")

    st.balance, st.frozen_balance = round(st.balance - max_c_share, 2), round(st.frozen_balance + max_c_share, 2)
    duel = Duel(creator_id=current_user.id, map_name=data.get('map_name', 'aim_redline'), total_bank=bank,
                creator_share=max_c_share, guest_share=round(bank - max_c_share, 2),
                min_rank=int(data.get('min_rank', 1)), max_rank=int(data.get('max_rank', 10)),
                is_private=bool(data.get('is_private', False)))
    db.add(duel)
    db.commit()
    return {"status": "success", "duel_id": duel.id}


@app.get("/api/v1/duels", response_model=list[DuelLobbyResponse], tags=["Matchmaking"])
async def list_lobbies(db: Session = Depends(get_db)):
    return [{
        "id": d.id, "map_name": d.map_name, "total_bank": d.total_bank, "min_rank": d.min_rank, "max_rank": d.max_rank,
        "creator_username": db.query(User.username).filter(User.id == d.creator_id).scalar(),
        "creator_elo": db.query(UserStats.elo).filter(UserStats.user_id == d.creator_id).scalar(),
        "creator_rank": get_rank_from_elo(db.query(UserStats.elo).filter(UserStats.user_id == d.creator_id).scalar())
    } for d in db.query(Duel).filter(Duel.status == 'waiting', Duel.is_private == False).all()]


@app.get("/api/v1/duels/{duel_id}", response_model=DuelDetailsResponse, tags=["Matchmaking"])
async def get_duel_details(duel_id: int, db: Session = Depends(get_db)):
    duel = get_duel_or_404(duel_id, db)
    return serialize_duel(duel, db)


@app.post("/api/v1/duels/{duel_id}/request", tags=["Matchmaking"])
async def create_duel_request(duel_id: int, current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    duel = get_duel_or_404(duel_id, db)
    if duel.creator_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot join your own duel")
    if duel.status != "waiting":
        raise HTTPException(status_code=400, detail="This duel is no longer accepting requests")
    if duel.guest_id:
        raise HTTPException(status_code=400, detail="This duel already has an opponent")

    current_stats = get_user_stats_or_404(current_user.id, db)
    check_active_match_existence(current_user.id, db)
    if current_stats.balance < duel.guest_share:
        raise HTTPException(status_code=400, detail="Insufficient margin balance")
    if not db.query(DuelRequest).filter(
        DuelRequest.duel_id == duel.id, DuelRequest.guest_id == current_user.id, DuelRequest.status == "pending"
    ).first():
        db.add(DuelRequest(duel_id=duel.id, guest_id=current_user.id))
        db.commit()
    return {"status": "success"}


@app.get("/api/v1/duels/{duel_id}/requests", response_model=list[DuelRequestResponse], tags=["Matchmaking"])
async def list_duel_requests(duel_id: int, current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    duel = get_duel_or_404(duel_id, db)
    if duel.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the duel creator can review requests")
    requests_list = db.query(DuelRequest).filter(DuelRequest.duel_id == duel.id, DuelRequest.status == "pending").all()
    payload = []
    for item in requests_list:
        guest = db.query(User).filter(User.id == item.guest_id).first()
        guest_stats = get_user_stats_or_404(item.guest_id, db)
        payload.append({
            "request_id": item.id,
            "guest_id": item.guest_id,
            "username": guest.username if guest else "Unknown",
            "avatar": guest.avatar if guest else "",
            "elo": guest_stats.elo,
            "rank": get_rank_from_elo(guest_stats.elo),
        })
    return payload


@app.post("/api/v1/requests/{req_id}/accept", tags=["Matchmaking"])
async def accept_duel_request(req_id: int, current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    req = db.query(DuelRequest).filter(DuelRequest.id == req_id, DuelRequest.status == "pending").first()
    if not req:
        raise HTTPException(status_code=404, detail="Duel request not found")
    duel = get_duel_or_404(req.duel_id, db)
    if duel.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the duel creator can accept requests")
    if duel.status != "waiting" or duel.guest_id:
        raise HTTPException(status_code=400, detail="This duel can no longer accept requests")

    guest_stats = get_user_stats_or_404(req.guest_id, db)
    if guest_stats.balance < duel.guest_share:
        raise HTTPException(status_code=400, detail="Opponent balance is no longer sufficient")

    guest_stats.balance = round(guest_stats.balance - duel.guest_share, 2)
    guest_stats.frozen_balance = round(guest_stats.frozen_balance + duel.guest_share, 2)
    duel.guest_id = req.guest_id
    duel.status = "ready"
    req.status = "accepted"

    db.query(DuelRequest).filter(DuelRequest.duel_id == duel.id, DuelRequest.id != req.id).update(
        {"status": "declined"}, synchronize_session=False
    )
    db.commit()
    return {"status": "success"}


@app.delete("/api/v1/duels/{duel_id}/cancel", tags=["Matchmaking"])
async def cancel_duel(duel_id: int, current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    duel = get_duel_or_404(duel_id, db)
    if duel.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the duel creator can cancel this duel")
    if duel.status != "waiting":
        raise HTTPException(status_code=400, detail="Only waiting duels can be cancelled")

    creator_stats = get_user_stats_or_404(duel.creator_id, db)
    creator_stats.balance = round(creator_stats.balance + duel.creator_share, 2)
    creator_stats.frozen_balance = round(max(0.0, creator_stats.frozen_balance - duel.creator_share), 2)
    db.query(DuelRequest).filter(DuelRequest.duel_id == duel.id, DuelRequest.status == "pending").update(
        {"status": "declined"}, synchronize_session=False
    )
    db.delete(duel)
    db.commit()
    return {"status": "success"}


@app.post("/api/v1/duels/{duel_id}/confirm", tags=["Matchmaking"])
async def confirm_duel_payout(duel_id: int, current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    duel = get_duel_or_404(duel_id, db)
    if current_user.id not in {duel.creator_id, duel.guest_id}:
        raise HTTPException(status_code=403, detail="Only match participants can confirm a payout")
    if duel.status not in {"processing", "ready", "playing"}:
        raise HTTPException(status_code=400, detail="This duel cannot be confirmed right now")

    creator_stats = get_user_stats_or_404(duel.creator_id, db)
    guest_stats = get_user_stats_or_404(duel.guest_id, db) if duel.guest_id else None
    winner_id = duel.winner_id or duel.creator_id
    winner_stats = creator_stats if winner_id == duel.creator_id else guest_stats
    loser_stats = guest_stats if winner_id == duel.creator_id else creator_stats
    commission_percent = get_current_commission(db)
    payout_amount = round(duel.total_bank * (1 - commission_percent / 100), 2)

    creator_stats.frozen_balance = round(max(0.0, creator_stats.frozen_balance - duel.creator_share), 2)
    if guest_stats:
        guest_stats.frozen_balance = round(max(0.0, guest_stats.frozen_balance - duel.guest_share), 2)
    if winner_stats:
        winner_stats.balance = round(winner_stats.balance + payout_amount, 2)
        winner_stats.wins += 1
        winner_stats.elo += 20
    if loser_stats:
        loser_stats.elo = max(700, loser_stats.elo - 20)
    creator_stats.duels += 1
    if guest_stats:
        guest_stats.duels += 1
    duel.status = "completed"
    duel.ended_at = datetime.utcnow()
    db.commit()
    return {"status": "success"}


@app.post("/api/v1/duels/{duel_id}/dispute", tags=["Matchmaking"])
async def dispute_duel(duel_id: int, current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    duel = get_duel_or_404(duel_id, db)
    if current_user.id not in {duel.creator_id, duel.guest_id}:
        raise HTTPException(status_code=403, detail="Only match participants can dispute this duel")
    if duel.status not in {"ready", "playing", "processing"}:
        raise HTTPException(status_code=400, detail="This duel cannot be disputed right now")
    duel.status = "disputed"
    db.commit()
    return {"status": "success"}


# ==================== GATES AND PAYMENTS SYSTEM ====================

@app.get("/api/v1/payments/methods", response_model=list[PaymentMethodResponse], tags=["Payments"])
async def get_payment_methods(type: str, db: Session = Depends(get_db)):
    return db.query(PaymentMethod).filter(PaymentMethod.type == type, PaymentMethod.is_active == True).all()


@app.post("/api/v1/payments/deposit", tags=["Payments"])
async def create_deposit(data: dict, current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    amount = float(data.get("amount", 0))
    method_id = int(data.get("method_id", 0))

    existing_tx = db.query(TransactionHistory).filter(
        TransactionHistory.user_id == current_user.id,
        TransactionHistory.type == "deposit",
        TransactionHistory.status == "pending"
    ).first()
    if existing_tx:
        raise HTTPException(status_code=400, detail="You already have an active pending invoice. Cancel it first.")

    method = db.query(PaymentMethod).filter(PaymentMethod.id == method_id, PaymentMethod.type == 'deposit',
                                            PaymentMethod.is_active == True).first()
    if not method: raise HTTPException(status_code=404, detail="Payment method not available")
    if amount < method.min_amount: raise HTTPException(status_code=400,
                                                       detail=f"Minimum deposit is ${method.min_amount}")

    charge_amount = round(amount * (1 + method.commission_percent / 100), 2)

    if method.gateway_alias == "cryptobot":
        headers = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN}
        payload = {
            "currency_type": "crypto",
            "asset": "USDT",
            "amount": str(charge_amount),
            "description": f"Platform Services Allocation for User #{current_user.id}",
            "paid_btn_name": "callback",
            "paid_btn_url": "https://likeagod.net/main"
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{CRYPTO_PAY_API_URL}/createInvoice", json=payload, headers=headers)
            if response.status_code != 200: raise HTTPException(status_code=500,
                                                                detail="CryptoPay API connection error")
            res_data = response.json()
            if not res_data.get("ok"): raise HTTPException(status_code=500, detail="Invoice rejected")
            invoice = res_data["result"]

            tx = TransactionHistory(user_id=current_user.id, amount=amount, currency="USDT", type="deposit",
                                    status="pending", payment_id=str(invoice["invoice_id"]),
                                    address=invoice["bot_invoice_url"])
            db.add(tx)
            db.commit()
            return {"pay_url": invoice["bot_invoice_url"]}

    elif method.gateway_alias == "aaio_rub":
        rub_amount = round(charge_amount * 90.0, 2)
        tx = TransactionHistory(user_id=current_user.id, amount=amount, currency="RUB", type="deposit",
                                status="pending")
        db.add(tx)
        db.commit()
        db.refresh(tx)

        signature_str = f"{AAIO_MERCHANT_ID}:{rub_amount}:RUB:{AAIO_SECRET_1}:{tx.id}"
        signature = hashlib.sha256(signature_str.encode('utf-8')).hexdigest()
        pay_url = f"https://aaio.so/merchant/pay?merchant_id={AAIO_MERCHANT_ID}&amount={rub_amount}&currency=RUB&order_id={tx.id}&sign={signature}&desc=Deposit+User+{current_user.id}&lang=ru"

        tx.address = pay_url
        db.commit()
        return {"pay_url": pay_url}

    raise HTTPException(status_code=400, detail="Unsupported gateway configuration")


@app.post("/api/v1/payments/cancel", tags=["Payments"])
async def cancel_pending_deposit(current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    tx = db.query(TransactionHistory).filter(
        TransactionHistory.user_id == current_user.id,
        TransactionHistory.type == "deposit",
        TransactionHistory.status == "pending"
    ).first()

    if not tx: raise HTTPException(status_code=404, detail="No active pending deposits found.")

    if tx.payment_id and tx.currency == "USDT":
        headers = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN}
        payload = {"invoice_id": int(tx.payment_id)}
        try:
            async with httpx.AsyncClient() as client:
                await client.post(f"{CRYPTO_PAY_API_URL}/deleteInvoice", json=payload, headers=headers)
        except:
            pass

    tx.status = "failed"
    db.commit()
    return {"status": "success", "message": "Invoice cancelled successfully."}


@app.get("/api/v1/payments/history", response_model=list[PaymentHistoryEntry], tags=["Payments"])
async def get_payment_history(current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    history = db.query(TransactionHistory).filter(TransactionHistory.user_id == current_user.id).order_by(
        TransactionHistory.created_at.desc()).all()
    return [{
        "id": tx.id, "amount": tx.amount, "currency": tx.currency, "type": tx.type, "status": tx.status,
        "date": tx.created_at.strftime("%Y-%m-%d %H:%M"), "address": tx.address
    } for tx in history]


@app.post("/api/v1/payments/webhook", tags=["Payments"])
async def crypto_pay_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    if body.get("update_type") == "invoice_paid":
        invoice = body["payload"]
        invoice_id = str(invoice["invoice_id"])
        tx = db.query(TransactionHistory).filter(TransactionHistory.payment_id == invoice_id,
                                                 TransactionHistory.status == 'pending').first()
        if tx:
            tx.status = 'completed'
            user_stats = db.query(UserStats).filter(UserStats.user_id == tx.user_id).first()
            if user_stats: user_stats.balance = round(user_stats.balance + tx.amount, 2)
            db.commit()
    return {"status": "ok"}


# ==================== CONTENT, PREMIUM AND ADMIN TOOLS ====================

@app.get("/news", response_model=list[NewsResponse], tags=["Public Content Engine"])
async def list_news(db: Session = Depends(get_db)):
    return db.query(News).order_by(News.created_at.desc()).all()


@app.post("/news/create", tags=["Admin"])
async def create_news(data: dict, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    title = str(data.get("title", "")).strip()
    image_path = str(data.get("image_path", "")).strip()
    if not title or not image_path:
        raise HTTPException(status_code=400, detail="Title and image are required")

    news = News(
        title=title[:120],
        image_path=image_path,
        btn_text=str(data.get("btn_text") or "").strip() or None,
        btn_url=str(data.get("btn_url") or "").strip() or None,
    )
    db.add(news)
    db.commit()
    db.refresh(news)
    return {"status": "success", "id": news.id}


@app.delete("/news/{news_id}", tags=["Admin"])
async def delete_news(news_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    news = db.query(News).filter(News.id == news_id).first()
    if not news:
        raise HTTPException(status_code=404, detail="News item not found")
    db.delete(news)
    db.commit()
    return {"status": "success"}


@app.get("/api/v1/premium/tariffs", response_model=list[TariffResponse], tags=["Premium"])
async def get_premium_tariffs(db: Session = Depends(get_db)):
    return db.query(PremiumTariff).order_by(PremiumTariff.duration_months.asc()).all()


@app.post("/api/v1/premium/buy", tags=["Premium"])
async def buy_premium(data: dict, current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    tariff = db.query(PremiumTariff).filter(PremiumTariff.id == int(data.get("tariff_id", 0))).first()
    if not tariff:
        raise HTTPException(status_code=404, detail="Premium tariff not found")
    stats = get_user_stats_or_404(current_user.id, db)
    if stats.balance < tariff.price:
        raise HTTPException(status_code=400, detail="Insufficient balance for premium purchase")

    stats.balance = round(stats.balance - tariff.price, 2)
    current_user.is_premium = True
    base_date = current_user.premium_until if current_user.premium_until and current_user.premium_until > datetime.utcnow() else datetime.utcnow()
    current_user.premium_until = base_date + timedelta(days=30 * tariff.duration_months)
    db.commit()
    return {"status": "success", "premium_until": current_user.premium_until}


@app.post("/api/v1/admin/adjust-balance", tags=["Admin"])
async def admin_adjust_balance(data: dict, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = find_user_by_target(str(data.get("target", "")).strip(), db)
    stats = get_user_stats_or_404(user.id, db)
    amount = float(data.get("amount", 0))
    stats.balance = round(stats.balance + amount, 2)
    db.commit()
    return {"status": "success", "message": f"Balance updated for {user.username}"}


@app.post("/api/v1/admin/adjust-elo", tags=["Admin"])
async def admin_adjust_elo(data: dict, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = find_user_by_target(str(data.get("target", "")).strip(), db)
    stats = get_user_stats_or_404(user.id, db)
    stats.elo = max(700, int(data.get("amount", stats.elo)))
    db.commit()
    return {"status": "success", "message": f"ELO updated for {user.username}"}


@app.post("/api/v1/admin/tariffs", tags=["Admin"])
async def admin_upsert_tariff(data: dict, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    duration_months = int(data.get("duration_months", 0))
    price = float(data.get("price", 0))
    if duration_months <= 0 or price <= 0:
        raise HTTPException(status_code=400, detail="Invalid tariff values")
    tariff = db.query(PremiumTariff).filter(PremiumTariff.duration_months == duration_months).first()
    if not tariff:
        tariff = PremiumTariff(duration_months=duration_months, price=price)
        db.add(tariff)
    tariff.price = price
    tariff.discount_text = str(data.get("discount_text") or "").strip() or None
    db.commit()
    return {"status": "success"}


@app.post("/api/v1/admin/commission", tags=["Admin"])
async def admin_update_commission(data: dict, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    commission_percent = float(data.get("commission_percent", 10.0))
    if commission_percent < 0 or commission_percent > 100:
        raise HTTPException(status_code=400, detail="Commission must be between 0 and 100")
    settings = db.query(PlatformSettings).first()
    if not settings:
        settings = PlatformSettings(commission_percent=commission_percent)
        db.add(settings)
    settings.commission_percent = commission_percent
    db.commit()
    return {"status": "success", "commission_percent": settings.commission_percent}


# ==================== MAIN APPLICATION ENGINE LOAD ====================

@app.get("/api/main", response_model=MainPayloadResponse, tags=["Public Content Engine"])
async def get_landing_page_payload(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    news = db.query(News).order_by(News.created_at.desc()).limit(10).all()
    news_payload = [
        {"id": n.id, "title": n.title, "image_path": n.image_path, "btn_text": n.btn_text, "btn_url": n.btn_url,
         "created_at": n.created_at} for n in news]
    commission = get_current_commission(db)

    my_duels_payload = []
    if current_user:
        my_duels = db.query(Duel).filter(((Duel.creator_id == current_user.id) | (Duel.guest_id == current_user.id)),
                                         Duel.status.in_(
                                             ['waiting', 'ready', 'playing', 'processing', 'disputed'])).all()
        for d in my_duels:
            creator = db.query(User).filter(User.id == d.creator_id).first()
            guest = db.query(User).filter(User.id == d.guest_id).first() if d.guest_id else None
            my_duels_payload.append({"id": d.id, "status": d.status, "total_bank": d.total_bank,
                                     "creator_name": creator.username if creator else "Unknown",
                                     "guest_name": guest.username if guest else "Waiting..."})

    response = {"news": news_payload, "commission_percent": commission, "authenticated": False, "user": None,
                "stats": None, "my_duels": my_duels_payload}
    if current_user:
        st = db.query(UserStats).filter(UserStats.user_id == current_user.id).first()
        elo_val = st.elo if st else 1000

        response.update({"authenticated": True, "user": {
            "id": current_user.id, "username": current_user.username, "avatar": current_user.avatar,
            "balance": st.balance if st else 0.0, "is_premium": current_user.is_premium,
            "premium_until": current_user.premium_until, "theme": current_user.theme, "effects": current_user.effects,
            "country": current_user.country, "language": current_user.language
        }})
        if st: response["stats"] = {"duels": st.duels, "wins": st.wins, "kills": st.kills, "deaths": st.deaths,
                                    "elo_val": elo_val, "rank": get_rank_from_elo(elo_val),
                                    "winrate": round((st.wins / st.duels * 100) if st.duels > 0 else 0, 1)}
    return response


@app.post("/api/v1/payments/withdraw", tags=["Payments"])
async def create_withdrawal(data: dict, current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    amount = float(data.get("amount", 0))
    method_id = int(data.get("method_id", 0))
    raw_tg = str(data.get("address", "")).strip()

    # Очищаем от собачки, если ввели @username
    tg_identifier = raw_tg.replace("@", "")

    if not tg_identifier:
        raise HTTPException(status_code=400, detail="Telegram ID or Username is required.")

    method = db.query(PaymentMethod).filter(PaymentMethod.id == method_id, PaymentMethod.type == 'withdraw',
                                            PaymentMethod.is_active == True).first()
    if not method:
        raise HTTPException(status_code=404, detail="Withdrawal method not found.")

    if amount < method.min_amount:
        raise HTTPException(status_code=400, detail=f"Minimum withdrawal is ${method.min_amount}")

    # Проверка на наличие уже ожидающей заявки
    existing_payout = db.query(TransactionHistory).filter(
        TransactionHistory.user_id == current_user.id,
        TransactionHistory.type == "withdraw",
        TransactionHistory.status == "pending"
    ).first()
    if existing_payout:
        raise HTTPException(status_code=400, detail="You already have an active pending withdrawal request.")

    user_stats = db.query(UserStats).filter(UserStats.user_id == current_user.id).first()
    if not user_stats or user_stats.balance < amount:
        raise HTTPException(status_code=400, detail="Insufficient liquid balance to process payout.")

    # Списание с баланса (холдирование)
    user_stats.balance = round(user_stats.balance - amount, 2)
    db.commit()

    # Формируем боевой payload для реального CryptoBot
    is_numeric_id = tg_identifier.isdigit()
    transfer_payload = {
        "asset": "USDT",
        "amount": str(amount),
        "spend_id": f"payout_tx_{random.randint(100000, 99999999)}_{current_user.id}"
    }

    # Если ввели чистые цифры — шлем как user_id, если буквы — как username
    if is_numeric_id:
        transfer_payload["user_id"] = int(tg_identifier)
    else:
        transfer_payload["username"] = str(tg_identifier)

    headers = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN}

    tx = TransactionHistory(
        user_id=current_user.id,
        amount=amount,
        currency="USDT",
        type="withdraw",
        status="pending",
        address=f"TG: @{tg_identifier}" if not is_numeric_id else f"TG ID: {tg_identifier}"
    )
    db.add(tx)
    db.commit()

    try:
        response = requests.post(f"{CRYPTO_PAY_API_URL}/transfer", json=transfer_payload, headers=headers, timeout=8)
        res_data = response.json()

        if response.status_code == 200 and res_data.get("ok"):
            # ВСЁ ПРОШЛО УСПЕШНО
            tx.status = "completed"
            tx.payment_id = str(res_data["result"]["transfer_id"])
            db.commit()
            return {"status": "success",
                    "message": f"Success! Instant payout of ${amount} sent to your @CryptoBot wallet."}
        else:
            # ЕСЛИ КРИПТОБОТ ОТКЛОНИЛ ТРАНЗАКЦИЮ
            error_msg = res_data.get("error", {}).get("name", "TRANSFER_FAILED")

            # МГНОВЕННЫЙ РОЛЛБЭК БАЛАНСА ИГРОКУ
            user_stats.balance = round(user_stats.balance + amount, 2)
            tx.status = "failed"

            if error_msg == "USER_NOT_FOUND" or error_msg == "USER_ID_REQUIRED":
                tx.address += f" (Rejected: User not found or privacy blocked)"
                db.commit()
                return {
                    "status": "failed",
                    "message": "Transfer rejected! CryptoBot cannot find this username (due to your privacy settings or registration status). Please try using your numeric Telegram ID instead. Money refunded."
                }
            else:
                tx.address += f" (Error: {error_msg})"
                db.commit()
                return {"status": "failed",
                        "message": f"Transfer rejected by gateway ({error_msg}). Your funds have been instantly refunded."}

    except Exception as e:
        # Сетевой таймаут — оставляем в pending для безопасности
        return {"status": "success", "message": "Payout is processing. Waiting for network confirmation."}

import test_front

app.router.routes.extend(test_front.router.routes)