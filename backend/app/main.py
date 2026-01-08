# app/main.py
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from api_router import api_router
from app.db.startup import sync_sequences  # ✅ Import da função
from app.core.config import settings
from app.api.v1.endpoints.company import router as company_router

app = FastAPI(
    title="TAFON API",
    version="1.0.0",
    description="API multi-tenant para gestão de almoxarifado, ativos e clientes."
)


@app.on_event("startup")
def on_startup():
    try:
        sync_sequences()
    except Exception as e:
        print(f"⚠️  Aviso: não foi possível sincronizar as sequências — {e}")
    # chamar show_config se existir (opcional)
    try:
        if hasattr(settings, "show_config"):
            settings.show_config()
    except Exception as e:
        print(f"⚠️  Aviso ao mostrar configurações: {e}")


# Build origins list from env var ALLOWED_ORIGINS (comma separated).
# If not set, fallback to localhost dev origins.
_raw_origins = os.getenv("ALLOWED_ORIGINS", "")
if _raw_origins:
    ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]
else:
    ALLOWED_ORIGINS = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure static / uploads directories exist before mounting (prevents runtime error)
Path("static/logos").mkdir(parents=True, exist_ok=True)
Path("static/imagens").mkdir(parents=True, exist_ok=True)
Path("uploads").mkdir(parents=True, exist_ok=True)

# Static mounts
app.mount("/static/logos", StaticFiles(directory="static/logos"), name="logos")
app.mount("/static/imagens", StaticFiles(directory="static/imagens"), name="fotos")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Routers
api_router.include_router(company_router)
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
def root():
    return {"message": "API SaaS rodando com sucesso!"}


@app.get("/health")
def health():
    """
    Health check simples — retorna 200 se a app estiver rodando.
    (Para checagem de DB, expanda com uma verificação de conexão.)
    """
    return {"status": "ok"}


# ---------- Endpoint temporário de debug de rotas ----------
@app.get("/_debug_routes")
def _debug_routes():
    """
    Lista todas as rotas registradas: path, métodos e nome.
    Atenção: endpoint temporário — remova após o debug.
    """
    routes = []
    for r in app.routes:
        try:
            routes.append({
                "path": getattr(r, "path", None),
                "name": getattr(r, "name", None),
                "methods": sorted(list(getattr(r, "methods", []) or [])),
            })
        except Exception:
            continue
    return {"routes": routes}