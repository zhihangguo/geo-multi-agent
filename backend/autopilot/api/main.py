"""
自动驾驶评估微服务 FastAPI 入口

运行方式:
    cd backend/autopilot
    python -m uvicorn api.main:create_fast_api --factory --host 127.0.0.1 --port 8002 --reload
"""
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import router


def create_fast_api() -> FastAPI:
    app = FastAPI(
        title="GeoAssist 自动驾驶评估服务",
        description="处理和分析自动驾驶海量数据，提供 Text2SQL、向量搜索、安全统计等能力",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    return app


if __name__ == "__main__":
    uvicorn.run(
        app=create_fast_api(),
        host="127.0.0.1",
        port=8002,
    )
