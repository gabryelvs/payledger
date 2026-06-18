from fastapi import FastAPI

from app.routers import auth

app = FastAPI(title="PayLedger", version="0.1.0")

app.include_router(auth.router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
