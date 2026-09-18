import logging
import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .db import UPLOAD_DIR, init_db
from .routers import auth, labels, notes, settings, themes, uploads

logging.basicConfig(level=logging.INFO)

init_db()

app = FastAPI(title="Keeply API", docs_url="/api/docs", openapi_url="/api/openapi.json")

allowed_origins = [s.strip() for s in (os.getenv("CORS_ORIGIN") or "").split(",") if s.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"error": "Invalid request payload"})


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    logging.exception("Unhandled error")
    return JSONResponse(status_code=500, content={"error": "Internal server error"})


@app.get("/api/health")
def health():
    import time

    return {"ok": True, "time": int(time.time() * 1000)}


app.include_router(auth.router, prefix="/api/auth")
app.include_router(notes.router, prefix="/api/notes")
app.include_router(labels.router, prefix="/api/labels")
app.include_router(uploads.router, prefix="/api/uploads")
app.include_router(themes.router, prefix="/api/themes")
app.include_router(settings.router, prefix="/api/settings")


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 4000)),
        reload=os.getenv("RELOAD") == "1",
    )
