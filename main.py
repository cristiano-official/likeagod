import os
import requests
import jwt
import random
import hashlib
import httpx
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import FastAPI, Request, HTTPException, Depends, Header
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pysteamsignin.steamsignin import SteamSignIn
from dotenv import load_dotenv

from models import User, UserStats, Duel, Base, News, DuelRequest, PremiumTariff, TransactionHistory, PlatformSettings, \
    PaymentMethod
from database import engine, session_local

load_dotenv()

app = FastAPI(
    title="LikeGod Esports Tournament Platform Core API",
    description="Backend engine for competitive esports matchmaking, player statistics tracking and platform events allocation.",
    version="1.9.7",
    docs_url="/docs"
)

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


@app.get("/user/me", tags=["User Profile"])
async def get_my_info(current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    st = db.query(UserStats).filter(UserStats.user_id == current_user.id).first()

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
        "rank": max(1, min(10, (st.elo - 700) // 100)),
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


@app.get("/user/by-name/{username}", tags=["User Profile"])
async def get_public_profile(username: str, request: Request, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.username == username).first()
    if not u: raise HTTPException(status_code=404, detail="Profile not found")
    st = db.query(UserStats).filter(UserStats.user_id == u.id).first()
    curr = get_current_user(request, db)
    return {
        "id": u.id, "username": u.username, "avatar": u.avatar, "bio": u.bio, "country": u.country,
        "is_premium": u.is_premium,
        "stats": {"duels": st.duels, "wins": st.wins, "kills": st.kills, "deaths": st.deaths, "elo": st.elo,
                  "rank": max(1, min(10, (st.elo - 700) // 100)),
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


@app.get("/api/v1/duels", tags=["Matchmaking"])
async def list_lobbies(db: Session = Depends(get_db)):
    return [{
        "id": d.id, "map_name": d.map_name, "total_bank": d.total_bank, "min_rank": d.min_rank, "max_rank": d.max_rank,
        "creator_username": db.query(User.username).filter(User.id == d.creator_id).scalar(),
        "creator_elo": db.query(UserStats.elo).filter(UserStats.user_id == d.creator_id).scalar(),
        "creator_rank": max(1, min(10, (
                    db.query(UserStats.elo).filter(UserStats.user_id == d.creator_id).scalar() - 700) // 100))
    } for d in db.query(Duel).filter(Duel.status == 'waiting', Duel.is_private == False).all()]


# ==================== GATES AND PAYMENTS SYSTEM ====================

@app.get("/api/v1/payments/methods", tags=["Payments"])
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


@app.get("/api/v1/payments/history", tags=["Payments"])
async def get_payment_history(current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    history = db.query(TransactionHistory).filter(TransactionHistory.user_id == current_user.id).order_by(
        TransactionHistory.created_at.desc()).all()
    return [{
        "id": tx.id, "amount": tx.amount, "currency": tx.currency, "type": tx.type, "status": tx.status,
        "date": tx.created_at.strftime("%Y-%m-%d %H:%M")
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


# ==================== LEGAL COMPLIANCE STATIC GATES ====================

# ==================== LEGAL COMPLIANCE STATIC GATES ====================

@app.get("/terms", response_class=HTMLResponse, tags=["Legal"])
async def render_terms():
    return """
    <html>
    <head>
        <title>Terms of Service | LikeGod.net</title>
        <style>
            body { font-family: 'Segoe UI', sans-serif; background: #121214; color: #fff; padding: 40px; line-height: 1.6; }
            .box { max-width: 900px; margin: 0 auto; background: #1a1a1e; padding: 40px; border-radius: 12px; border: 1px solid #2d2d34; box-shadow: 0 4px 20px rgba(0,0,0,0.5); position: relative; }
            h1 { color: #4CAF50; font-size: 24px; text-align: center; text-transform: uppercase; margin-bottom: 5px; }
            .subtitle { text-align: center; color: #94a3b8; font-size: 14px; margin-bottom: 30px; }
            .warning-box { background: #221515; border: 1px solid #ef4444; padding: 15px; border-radius: 6px; color: #f43f5e; font-size: 13px; margin-bottom: 30px; }
            h2 { color: #4CAF50; font-size: 18px; border-bottom: 1px solid #2d2d34; padding-bottom: 8px; margin-top: 30px; }
            ul { padding-left: 20px; }
            li { margin-bottom: 10px; }
            .strong-term { color: #60a5fa; }
            .back-btn { background: #2d2d34; color: #fff; border: 1px solid #444; padding: 10px 20px; border-radius: 6px; text-decoration: none; display: inline-block; font-weight: bold; margin-top: 20px; transition: 0.2s; }
            .back-btn:hover { background: #4CAF50; border-color: #4CAF50; }

            /* Стили для кнопки переключения языков */
            .lang-switcher {
                position: absolute;
                top: 20px;
                right: 20px;
                background: #2d2d34;
                border: 1px solid #444;
                color: #fff;
                padding: 6px 14px;
                border-radius: 6px;
                cursor: pointer;
                font-weight: bold;
                font-size: 13px;
                transition: 0.2s;
            }
            .lang-switcher:hover { background: #4CAF50; border-color: #4CAF50; }

            .lang-section { display: none; }
            .active-lang { display: block; }
        </style>
    </head>
    <body>
        <div class="box">
            <!-- Кнопка переключения -->
            <button class="lang-switcher" id="langBtn" onclick="toggleLanguage()">Перейти на Русский</button>

            <!-- ========================================== ENGLISH VERSION ========================================== -->
            <div id="lang-en" class="lang-section active-lang">
                <h1>Public Offer & Terms of Service</h1>
                <div class="subtitle">Esports Competition Management Infrastructure «LikeGod.net»</div>

                <div class="warning-box">
                    <strong>USER NOTICE:</strong> This document is an official legal proposal (public offer). Registering an Account, utilizing Platform infrastructure, depositing funds, or participating in matches implies your absolute, unconditional agreement to all clauses listed below. If you do not agree with any statement, you must immediately terminate usage and leave the Site.
                </div>

                <h2>1. TERMS AND DEFINITIONS</h2>
                <ul>
                    <li><strong class="strong-term">Operator (Organizer)</strong> — Individual Entrepreneur Moskalenko A. A., managing the Platform, providing server configurations for esports matchmaking, and serving as a technical escrow and distribution agent for the Prize Pool.</li>
                    <li><strong class="strong-term">User (Player)</strong> — An individual aged 14 or older who completed registration. Minors between 14-18 access the services with explicit consent of their legal guardians.</li>
                    <li><strong class="strong-term">Platform (Site)</strong> — The system located at «LikeGod.net», facilitating software-driven tournament operations.</li>
                    <li><strong class="strong-term">Competition (Duel / Match)</strong> — A match inside Counter-Strike 2 (CS2) evaluated purely on individual skill (skill-based performance). This event is legally defined under Art. 1055 of the Civil Code of the Russian Federation (Public Promise of a Reward) and strictly does not constitute gambling, betting, or lottery.</li>
                    <li><strong class="strong-term">Lobby</strong> — A dynamic entry created by a User specifying entry parameters, rank constraints, and the Participation Entry Fee.</li>
                    <li><strong class="strong-term">Participation Entry Fee</strong> — Liquid funds allocated and held on the User Account balance to confirm intent and form the absolute Prize Pool for a specific match.</li>
                    <li><strong class="strong-term">Prize Pool (Reward)</strong> — Aggregated Entry Fees for a specific Match, due for distribution to the Winner minus the Platform Service Fee.</li>
                    <li><strong class="strong-term">User Account (Balance)</strong> — An internal database accounting ledger reflecting advance deposits and authorized prize distribution credits.</li>
                    <li><strong class="strong-term">Service Fee</strong> — Infrastructure allocation compensation retained by the Operator at the time of Prize Pool distribution.</li>
                </ul>

                <h2>2. SUBJECT OF THE AGREEMENT</h2>
                <p>2.1. The Operator grants access to software utilities on «LikeGod.net» for setting up skill-based Counter-Strike 2 competitive duels, while the User agrees to follow code-enforced rules and cover Service Fees accordingly.</p>
                <p>2.2. The Operator guarantees technical recording of game engine output data, internal balance tracking, fee deduction, and match dispute arbitration services.</p>
                <p>2.3. The User explicitly acknowledges that all match resolutions depend fully on personal mechanical skills. Random chance components are entirely excluded; the platform operates no gambling variants.</p>

                <h2>3. ACCEPTANCE AND ACCOUNT VALIDATION</h2>
                <p>3.1. Valid signature and acceptance of this contract (pursuant to Art. 438 of the CC RF) occurs automatically when a user creates an account, initializes an incoming deposit invoice, or enters an active matchmaking lobby.</p>
                <p>3.2. Users below 18 warrant under Art. 431.2 of the CC RF that their deployment of liquid tokens originates from personal stipends or funds legally transferred by guardians for unconstrained use.</p>

                <h2>4. COMPETITION LOGICS AND PRIZE MECHANICS</h2>
                <p>4.1. A User may generate a Lobby entry by allocating a corresponding fee parameter. A second challenger binds the transaction by matching the entry settings.</p>
                <p>4.2. Upon mutual confirmation, matching stakes are locked from current account limits to construct the specific operational Prize Pool.</p>
                <p>4.3. Following the server match completion string parse, the system routes the Reward aggregate to the winning user, deducting the set Operator Service Fee.</p>
                <p>4.4. Accounting Architecture: Inbound accounting events are classified as advanced deposits. Revenue is declared solely based on the finalized Service Fees collected, while standard stakes act as transit asset pools.</p>

                <h2>5. FINANCES, OUTBOUND WITHDRAWALS, AND TAXATION</h2>
                <p>5.1. Operations are completed through external gateway providers. The Operator disclaims liability for gateway processing latencies or underlying channel fees.</p>
                <p>5.2. Return Protocols: Users maintain the right to initiate outbound settlements for unallocated, clear balance parameters back to their native initial source, net of confirmed processing overheads.</p>
                <p>5.3. Settled match transactions allocated based on server game logging logs are irreversible and cannot be refunded, unless a formal Dispute Appeal is approved.</p>
                <p>5.4. Taxation: Under Art. 224 and 228 of the Russian Tax Code, the recipient of a competitive reward independently declares and executes personal income tax (NDFL) filings. The platform is not a withholding tax agent.</p>

                <h2>6. DISPUTE AND ANTI-CHEAT ARBITRATION</h2>
                <p>6.1. If a User suspects client anomalies or malicious utility usage by an opponent, a Dispute Appeal must be logged inside 48 hours of match resolution.</p>
                <p>6.2. internal verification specialists review log files and game recordings. The Operator reserves absolute authority to balance states following adjudication; findings are terminal.</p>

                <h2>7. CODES OF CONDUCT AND INFRASTRUCTURE SAFETY</h2>
                <p>7.1. Malicious automation, reverse engineering, exploit code usage, cheat frameworks, match-fixing, or structural transaction manipulation violate basic service access rights.</p>
                <p>7.2. Code infractions authorize the Operator to terminate profile access permissions. Any ill-gotten credits are written off. Remaining clean initial non-allocated capital deposits are liquidated back via explicit offline verification.</p>

                <h2>8. DATA MANAGEMENT PRIVACY</h2>
                <p>8.1. Acceptance grants explicit processing permissions under Federal Law № 152-FZ «On Personal Data» concerning server logs, routing tokens, dynamic IP configurations, and payment keys.</p>

                <h2>9. LIMITATION OF LIABILITY</h2>
                <p>9.1. Systems deploy on an "as is" baseline. The platform disclaims performance faults induced by Valve Corporation API drops, Steam account authentication limits, or general network congestion.</p>
                <p>9.2. Contentious issues require a 15-day amicable negotiation process. Unresolved items move to the court at the Operator's registration jurisdiction under standard Russian statutory law.</p>

                <h2>10. MERCHANT IDENTIFICATION DETAILS</h2>
                <p>
                    <strong>Merchant entity:</strong> Individual Entrepreneur Moskalenko A. A.<br>
                    <strong>Tax Registry ID (INN):</strong> 972904931221<br>
                    <strong>Support Telegram:</strong> <a href="https://t.me/likeagod_support" style="color: #4CAF50; text-decoration: none;">@likeagod_support</a><br>
                    <strong>Banking Protocols:</strong> Available strictly upon verified official request
                </p>
            </div>

            <!-- ========================================== RUSSIAN VERSION ========================================== -->
            <div id="lang-ru" class="lang-section">
                <h1>Публичная Оферта</h1>
                <div class="subtitle">интернет-платформы «LikeGod.net» по организации киберспортивных соревнований</div>

                <div class="warning-box">
                    <strong>ВНИМАНИЕ ПОЛЬЗОВАТЕЛЯ:</strong> Настоящий документ является официальным юридическим предложением (публичной офертой) индивидуального предпринимателя. Регистрация Личного кабинета, использование возможностей Платформы, внесение денежных средств или участие в киберспортивных соревнованиях означают ваше полное и безоговорочное согласие со всеми условиями настоящего Договора (Акцепт оферты). Если вы не согласны с каким-либо пунктом, вам надлежит немедленно покинуть Сайт.
                </div>

                <h2>1. ТЕРМИНЫ И ОПРЕДЕЛЕНИЯ</h2>
                <ul>
                    <li><strong class="strong-term">Исполнитель (Организатор)</strong> — Индивидуальный предприниматель Москаленко А. А., осуществляющий администрирование Платформы, обеспечение технической возможности проведения киберспортивных соревнований, а также выступающий в качестве технологического и платежного агента по распределению Призового фонда.</li>
                    <li><strong class="strong-term">Пользователь (Игрок)</strong> — физическое лицо, достигшее возраста 14 (четырнадцати) лет, прошедшее регистрацию на Платформе. Лица в возрасте от 14 до 18 лет осуществляют акцепт настоящей оферты с согласия своих законных представителей.</li>
                    <li><strong class="strong-term">Платформа (Сайт)</strong> — веб-сайт в сети Интернет под названием «LikeGod.net», представляющий собой программно-аппаратный комплекс для организации киберспортивных соревнований.</li>
                    <li><strong class="strong-term">Соревнование (Дуэль / Матч)</strong> — соревновательное мероприятие по дисциплине Counter-Strike 2 (CS2), проводимое между Пользователями на Платформе на условиях демонстрации персональных игровых навыков (skill-based). Данное мероприятие регламентируется ст. 1055 ГК РФ (Публичное обещание награды), не является азартной игрой, пари или лотереей.</li>
                    <li><strong class="strong-term">Лобби</strong> — виртуальная комната матча, создаваемая Пользователем, в которой определяются параметры будущего Соревнования, включая требования к рангу и Обеспечительный взнос.</li>
                    <li><strong class="strong-term">Обеспечительный взнос (Взнос за участие)</strong> — сумма денежных средств, резервируемая на Учетном счете Пользователя в момент подтверждения участие в Соревновании, формирующая Призовой фонд.</li>
                    <li><strong class="strong-term">Призовой фонд (Награда)</strong> — сумма Обеспечительных взносов участников конкретного Соревнования, подлежащая выплате Победителю матча за вычетом Сервисного сбора Платформы.</li>
                    <li><strong class="strong-term">Учетный счет (Баланс)</strong> — виртуальный аналитический регистр внутри Платформы, отображающий объем авансовых платежей Пользователя, внесенных им для оплаты услуг Платформы.</li>
                    <li><strong class="strong-term">Сервисный сбор</strong> — вознаграждение Исполнителя за предоставление технической инфраструктуры Платформы, удерживаемое в момент распределения Призового фонда.</li>
                </ul>

                <h2>2. ПРЕДМЕТ ДОГОВОРА</h2>
                <p>2.1. Исполнитель предоставляет Пользователю доступ к программным возможностям Платформы «LikeGod.net» для организации и участия в киберспортивных соревнованиях (Дуэлях) по игре Counter-Strike 2, а Пользователь обязуется соблюдать правила Платформы и выплачивать Сервисный сбор в порядке, установленном настоящей Офертой.</p>
                <p>2.2. Исполнитель осуществляет техническую фиксацию результатов матчей, ведение Учетного счета Пользователей, удержание Сервисного сбора, а также выполнение функций арбитража в случае возникновения споров по результатам соревнований.</p>
                <p>2.3. Пользователь признает и подтверждает, что участие в соревнованиях на Платформе основано исключительно на демонстрации персональных игровых навыков. Платформа не проводит азартные игры (гэмблинг), лотереи, ставки на спорт или иные мероприятия, основанные на случайности.</p>

                <h2>3. ПОРЯДОК РЕГИСТРАЦИИ И АКЦЕПТ ОФЕРТЫ</h2>
                <p>3.1. Полным и безоговорочным принятием (Акцептом) условий настоящей Публичной оферты в соответствии со статьей 438 Гражданского кодекса РФ признается совершение Пользователем любого из следующих действий: а) регистрация учетной записи на Сайте; б) пополнение Учетного счета через Сервис приема платежей; в) создание Лобби или подтверждение вступления в Лобби другого Пользователя.</p>
                <p>3.2. Проходя регистрацию, Пользователь в возрасте от 14 до 18 лет гарантирует и подтверждает, что действует с согласия своих законных представителей (родителей, опекунов), а денежные средства, используемые на Платформе, являются его собственным заработком, стипендией или предоставлены законными представителями для свободного распоряжения в соответствии с п. 2 ст. 26 ГК РФ (Заверение об обстоятельствах по ст. 431.2 ГК РФ).</p>

                <h2>4. МЕХАНИКА СОРЕВНОВАНИЙ И ФОРМИРОВАНИЕ ПРИЗОВОГО ФОНДА</h2>
                <p>4.1. Один из Пользователей имеет право создать Лобби, самостоятельно установив Взнос за участие на основании доступных лимитов своего Учетного счета. Второй Пользователь принимает вызов, вступая в Лобби.</p>
                <p>4.2. В момент подтверждения готовности обоих Игроков, сумма Взноса за участие блокируется на Учетном счете каждого из участников. Сумма данных взносов формирует Призовой фонд текущего Соревнования.</p>
                <p>4.3. После завершения Матча в системе CS2 и автоматической или ручной фиксации результата Платформой, Победителю зачисляется Награда (Призовой фонд) за вычетом Сервисного сбора Платформы (комиссии Организатора).</p>
                <p>4.4. Юридическая схема расчетов: Денежные средства, вносимые на баланс, признаются авансовым платежом. Исполнитель признает своим доходом (выручкой) исключительно Сервисный сбор. Остальные средства признаются транзитными агентскими суммами, удерживаемыми в целях выплаты Победителю.</p>

                <h2>5. ФИНАНСОВЫЕ УСЛОВИЯ, ПОПОЛНЕНИЕ И ВЫВОД СРЕДСТВ</h2>
                <p>5.1. Пополнение Баланса и вывод денежных средств осуществляются через интегрированные сторонние платежные сервисы. Исполнитель не несет ответственности за задержки, сбои или комиссии, установленные указанными платежными сервисами.</p>
                <p>5.2. Правила возврата денежных средств: Пользователь имеет право в любой момент запросить возврат неизрасходованных (ранее внесенных лично и не заблокированных в активных матчах) денежных средств на те же реквизиты, с которых осуществлялось пополнение, за вычетом документально подтвержденных расходов на транзакции.</p>
                <p>5.3. Возврат денежных средств, которые были правомерно списаны в качестве Обеспечительного взноса по результатам завершенного матча в пользу Победителя, не производится, за исключением случаев удовлетворения Апелляции.</p>
                <p>5.4. Налогообложение: Согласно ст. 224 и ст. 228 Налогового кодекса РФ, Пользователь (получатель дохода в виде приза) самостоятельно исчисляет, декларирует и уплачивает налог на доходы физических лиц (НДФЛ) со своих выигрышей. Исполнитель не выступает в качестве налогового агента.</p>

                <h2>6. СИСТЕМА АПЕЛЛЯЦИЙ И РАССМОТРЕНИЕ СПОРОВ</h2>
                <p>6.1. В случае несогласия с техническим результатом Матча, зафиксированным Платформой, или при обнаружении фактов нечестной игры со стороны соперника, Пользователь имеет право подать официальную Апелляцию в течение 2 (двух) календарных дней (48 часов) с момента окончания Матча.</p>
                <p>6.2. Рассмотрение Апелляции осуществляется специализированной внутренней службой модерации Исполнителя. По результатам рассмотрения Исполнитель имеет право изменить статус матча и осуществить корректировку Балансов участников. Решение службы модерации является окончательным.</p>

                <h2>7. ПРАВИЛА ПОВЕДЕНИЯ И ЗАЩИТА ОТ ЗЛОУПОТРЕБЛЕНИЙ</h2>
                <p>7.1. Пользователю категорически запрещается использовать стороннее программное обеспечение (читы, макросы), применять мошеннические схемы (договорные матчи), использовать Платформу в целях легализации доходов, полученных преступным путем.</p>
                <p>7.2. В случае нарушения правил Исполнитель имеет право заблокировать Личный кабинет Пользователя. При этом призовые средства, полученные в результате нарушений, аннулируются. Неиспользованные личные денежные средства, ранее внесенные Пользователем на баланс, подлежат возврату по письменному заявлению за вычетом комиссий платежных систем и расходов Исполнителя.</p>

                <h2>8. ПЕРСОНАЛЬНЫЕ DАННЫЕ</h2>
                <p>8.1. Акцептуя оферту, Пользователь дает свое полное и добровольное согласие Исполнителю на обработку своих персональных данных (email, никнейм, платежные реквизиты, логи, IP-адрес) в соответствии с Федеральным законом № 152-ФЗ «О персональных данных» для целей исполнения настоящего Договора.</p>

                <h2>9. ОГРАНИЧЕНИЕ ОТВЕТСТВЕННОСТИ И ПРИМЕНИМОЕ ПРАВО</h2>
                <p>9.1. Платформа предоставляется по принципу «как есть». Исполнитель не несет ответственности за технические проблемы на стороне Valve (Counter-Strike 2), серверов Steam или провайдеров связи.</p>
                <p>9.2. Все споры и разногласия разрешаются сторонами путем переговоров (досудебный претензионный порядок 15 дней). В случае недостижения согласия спор передается на рассмотрение в суд по месту нахождения Исполнителя в соответствии с законодательством РФ.</p>
                <p>9.3. Исполнитель оставляет за собой право изменять условия оферты. Новая редакция вступает в силу через 3 (три) календарных дня после ее публикации на Сайте.</p>

                <h2>10. РЕКВИЗИТЫ ИСПОЛНИТЕЛЯ</h2>
                <p>
                    <strong>Исполнитель:</strong> Индивидуальный предприниматель Москаленко А. А.<br>
                    <strong>ИНН:</strong> 972904931221<br>
                    <strong>Support Telegram:</strong> <a href="https://t.me/likeagod_support" style="color: #4CAF50; text-decoration: none;">@likeagod_support</a><br>
                    <strong>Банковские реквизиты:</strong> Предоставляются по запросу
                </p>
            </div>

            <div style="text-align: center; margin-top: 40px;">
                <a href="/main" class="back-btn">← Return to Main</a>
            </div>
        </div>

        <script>
            function toggleLanguage() {
                const enSection = document.getElementById('lang-en');
                const ruSection = document.getElementById('lang-ru');
                const btn = document.getElementById('langBtn');

                if (enSection.classList.contains('active-lang')) {
                    enSection.classList.remove('active-lang');
                    ruSection.classList.add('active-lang');
                    btn.innerText = "Switch to English";
                } else {
                    ruSection.classList.remove('active-lang');
                    enSection.classList.add('active-lang');
                    btn.innerText = "Перейти на Русский";
                }
            }
        </script>
    </body>
    </html>
    """


@app.get("/refund", response_class=HTMLResponse, tags=["Legal"])
async def render_refund():
    return """
    <html><head><title>Refund Policy | LikeGod</title><style>body{font-family:sans-serif; background:#121214; color:#fff; padding:40px; line-height:1.6;} .box{max-width:800px; margin:0 auto; background:#1a1a1e; padding:30px; border-radius:8px;}</style></head>
    <body><div class="box"><h1>Refund & Cancellation Policy</h1>
    <h2>1. Service Utilization</h2><p>Digital services are considered fully provided upon delivery. Unused assets can be requested for liquidation payout via user control panel at any time. Canceled matches auto-refund 100% margin asset allocation value.</p>
    <br><a href="/main" style="color:#4CAF50; text-decoration:none;">← Back to Main</a></div></body></html>
    """


# ==================== MAIN APPLICATION ENGINE LOAD ====================

@app.get("/api/main", tags=["Public Content Engine"])
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
                                    "elo_val": elo_val, "rank": max(1, min(10, (elo_val - 700) // 100)),
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

app.include_router(test_front.router)