from fastapi import FastAPI

from app.modules.blog.router import router as blog_router

app = FastAPI(title="Marketplace Blog API")
app.include_router(blog_router, prefix="/api/v1")


# @app.get("/health")
# async def health():
#     return {"status": "ok"}
