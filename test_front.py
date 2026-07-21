from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter(tags=["Frontend"])

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"


def render_template(name: str) -> HTMLResponse:
    return HTMLResponse((TEMPLATES_DIR / name).read_text(encoding="utf-8"))


@router.get("/main", response_class=HTMLResponse)
async def render_main(request: Request):
    return render_template("index.html")


@router.get("/duels", response_class=HTMLResponse)
async def render_duels(request: Request):
    return render_template("duels.html")


@router.get("/duel", response_class=HTMLResponse)
async def render_duel_room(request: Request):
    return render_template("duel.html")


@router.get("/duel/invite/{token}", response_class=HTMLResponse)
async def render_duel_invite(token: str):
    return render_template("duel.html")


@router.get("/premium", response_class=HTMLResponse)
async def render_premium_shop(request: Request):
    return render_template("premium.html")


@router.get("/admin", response_class=HTMLResponse)
async def render_admin_dashboard(request: Request):
    return render_template("admin.html")


@router.get("/p/{username}", response_class=HTMLResponse)
async def render_public_profile(username: str):
    return render_template("profile.html")


@router.get("/terms", response_class=HTMLResponse)
async def render_terms(request: Request):
    return render_template("terms.html")


@router.get("/privacy", response_class=HTMLResponse)
async def render_privacy(request: Request):
    return render_template("privacy.html")


@router.get("/refund", response_class=HTMLResponse)
async def render_refund(request: Request):
    return render_template("refund.html")


@router.get("/")
async def root_redirect():
    return RedirectResponse(url="/main")
