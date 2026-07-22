from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.routers import agenda, auth, farmacia, medico, patients, salud, wallet

app = FastAPI(title="TODOSCARE API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(patients.router)
app.include_router(agenda.router)
app.include_router(salud.router)
app.include_router(farmacia.router)
app.include_router(wallet.router)
app.include_router(medico.router)

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
app.mount("/files", StaticFiles(directory=str(UPLOAD_DIR)), name="files")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
