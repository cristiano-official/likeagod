from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter(tags=["Test Frontend Engine"])

@router.get("/main", response_class=HTMLResponse)
async def render_main(request: Request):
    with open("templates/index.html", "r", encoding="utf-8") as f: return HTMLResponse(content=f.read())

@router.get("/duels", response_class=HTMLResponse)
async def render_duels(request: Request):
    with open("templates/duels.html", "r", encoding="utf-8") as f: return HTMLResponse(content=f.read())

@router.get("/duel", response_class=HTMLResponse)
async def render_duel_room(request: Request):
    with open("templates/duel.html", "r", encoding="utf-8") as f: return HTMLResponse(content=f.read())

@router.get("/premium", response_class=HTMLResponse)
async def render_premium_shop(request: Request):
    with open("templates/premium.html", "r", encoding="utf-8") as f: return HTMLResponse(content=f.read())

@router.get("/admin", response_class=HTMLResponse)
async def render_admin_dashboard(request: Request):
    with open("templates/admin.html", "r", encoding="utf-8") as f: return HTMLResponse(content=f.read())

@router.get("/p/{username}", response_class=HTMLResponse)
async def render_public_profile(username: str):
    with open("templates/profile.html", "r", encoding="utf-8") as f: return HTMLResponse(content=f.read())

# ЮРИДИЧЕСКИЕ СТРАНИЦЫ ДЛЯ МОДЕРАЦИИ LAVA
@router.get("/terms", response_class=HTMLResponse)
async def render_terms(request: Request):
    with open("templates/terms.html", "r", encoding="utf-8") as f: return HTMLResponse(content=f.read())

@router.get("/privacy", response_class=HTMLResponse)
async def render_privacy(request: Request):
    with open("templates/privacy.html", "r", encoding="utf-8") as f: return HTMLResponse(content=f.read())

@router.get("/refund", response_class=HTMLResponse)
async def render_refund(request: Request):
    with open("templates/refund.html", "r", encoding="utf-8") as f: return HTMLResponse(content=f.read())

@router.get("/")
async def root_redirect():
    return RedirectResponse(url="/main")