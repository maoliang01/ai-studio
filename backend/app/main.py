from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, models

app = FastAPI(
    title="AI Studio API",
    description="AI Studio 工作台后端 API",
    version="1.0.0",
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001", "http://127.0.0.1:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(chat.router)
app.include_router(models.router)


@app.get("/")
async def root():
    """API 根路径"""
    return {"message": "AI Studio API", "version": "1.0.0"}


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)