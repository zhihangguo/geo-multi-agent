"""

创建FastAPI实例 并且管理所有的路由

"""
import os
import logging
logging.basicConfig(level=logging.INFO)
logger=logging.getLogger(__name__)

# 修复：国内网络无法访问 openaipublic.blob.core.windows.net
# 设置 tiktoken 缓存目录，避免每次启动都尝试下载编码文件
_tiktoken_cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tiktoken_cache")
os.makedirs(_tiktoken_cache_dir, exist_ok=True)
os.environ["TIKTOKEN_CACHE_DIR"] = _tiktoken_cache_dir

import  uvicorn
from fastapi import FastAPI
from .routers import router
def  create_fast_api()->FastAPI:


    # 1. 创建FastApi实例
    app=FastAPI(title="Knowledge API")


    # 2. 注册各种路由
    app.include_router(router=router)

    # 3.返回创建的FastAPI
    return app



if __name__ == '__main__':
    print("1.准备启动Web服务器")
    try:
        uvicorn.run(app=create_fast_api(),host="127.0.0.1",port=8001)
        logger.info("2.启动Web服务器成功...")
    except KeyboardInterrupt as e:
        logger.error(f"2.启动Web服务器失败: {str(e)}")














