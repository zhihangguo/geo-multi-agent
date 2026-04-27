"""
Uvicorn 日志配置，抑制流式响应断开时的噪音错误
"""
import logging

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": "%(levelprefix)s %(message)s",
            "use_colors": None,
        },
        "access": {
            "()": "uvicorn.logging.AccessFormatter",
            "fmt": '%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s',
        },
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
        "access": {
            "formatter": "access",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "uvicorn": {"level": "INFO", "handlers": ["default"], "propagate": False},
        "uvicorn.error": {"level": "INFO", "handlers": ["default"], "propagate": False},
        "uvicorn.access": {"handlers": ["access"], "propagate": False},
        # 抑制 Chroma 遥测
        "chromadb.telemetry.product.posthog": {"level": "WARNING", "handlers": ["default"], "propagate": False},
    },
    "root": {"level": "INFO", "handlers": ["default"]},
}


def suppress_cancelled_error_filter(record):
    """过滤掉 CancelledError 相关的噪音日志"""
    msg = record.getMessage()
    if "CancelledError" in msg or "cancel scope" in msg:
        return False
    return True
