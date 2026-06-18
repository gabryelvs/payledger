from fastapi import FastAPI

from app.routers import accounts, auth

app = FastAPI(title="PayLedger", version="0.1.0")

app.include_router(auth.router)
app.include_router(accounts.router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
