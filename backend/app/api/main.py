import asyncio
import logging
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .routers import router
from .auth_router import router as auth_router
from infrastructure.logging.logger import logger
from infrastructure.tools.mcp.mcp_manager import mcp_connect, mcp_cleanup


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI应用生命周期管理

    在应用启动时建立MCP连接，在应用关闭时清理连接。
    确保资源正确初始化和释放。
    """
    # 应用启动时执行
    logger.info("应用启动，建立MCP连接...")
    try:
        await mcp_connect()
        logger.info("MCP连接建立完成")
    except Exception as e:
        logger.error(f"MCP连接建立失败: {str(e)}")

    try:
        yield  # 应用运行期间（先别释放mcp链接 去处理请求...）
    except asyncio.CancelledError:
        # 客户端断开连接时，ASGI lifespan可能被取消，这是正常行为
        pass

    # 应用关闭时执行
    logger.info("应用关闭，清理MCP连接...")
    try:
        await mcp_cleanup()
        logger.info("MCP连接清理完成")
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"MCP连接清理失败: {str(e)}")


def create_fast_api() -> FastAPI:
    # 1. 创建FastApi实例,绑定了生命周期事件
    app = FastAPI(title="ITS API", lifespan=lifespan)

    # 2. 处理跨域
    app.add_middleware(
        CORSMiddleware,
        # CORSMiddleware 会自动拦截后端的响应 并贴上这些标签 Access-Control-Allow-Origin Access-Control-Allow-Methods Access-Control-Allow-Headers
        allow_origins=["*"],  # 生产环境应限制为特定域名
        allow_credentials=True,  # cookie(自定义的key value)(user_id)
        allow_methods=["*"],  # 任意的请求都可以（POST）
        allow_headers=["*"],  # 请求头中带上自己的信息（token）
    )

    # 3. 注册各种路由
    app.include_router(router=router)
    app.include_router(router=auth_router)

    # 4.返回创建的FastAPI
    return app


if __name__ == '__main__':
    print("1.准备启动Web服务器")

    # 配置 uvicorn 日志：抑制 CancelledError 噪音
    for uv_logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        _uvlog = logging.getLogger(uv_logger_name)
        _uvlog.handlers.clear()
        _h = logging.StreamHandler()
        _h.setFormatter(uvicorn.logging.DefaultFormatter("%(levelprefix)s %(message)s"))
        _uvlog.addHandler(_h)
        _uvlog.setLevel(logging.INFO)
        _uvlog.addFilter(lambda r: not ("CancelledError" in r.getMessage() or "cancel scope" in r.getMessage() or " Cancelled " in r.getMessage()))

    try:
        uvicorn.run(
            app=create_fast_api(),
            host="127.0.0.1",
            port=8000,
            log_config=None,  # 禁用 uvicorn 默认日志配置，使用上面的自定义配置
        )

        logger.info("2.启动Web服务器成功...")

    except KeyboardInterrupt as e:
        logger.error(f"2.启动Web服务器失败: {str(e)}")
