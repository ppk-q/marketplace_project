from fastapi import FastAPI

app = FastAPI(title="Marketplace Blog API")


@app.get("/health")
async def health():
    return {"status": "ok"}
