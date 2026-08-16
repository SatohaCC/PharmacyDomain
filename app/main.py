from fastapi import FastAPI

app = FastAPI(title="PharmacyDomain API", version="0.1.0")


@app.get("/", tags=["system"])
def read_root() -> dict[str, str]:
    return {"message": "PharmacyDomain API is running"}


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
