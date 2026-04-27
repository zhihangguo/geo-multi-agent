"""
用户认证 API — 登录 / 注册 / 初始化默认用户
"""
import bcrypt
from pydantic import BaseModel, Field
from fastapi.routing import APIRouter
from starlette.responses import JSONResponse

from infrastructure.database.database_pool import DatabasePool
from infrastructure.logging.logger import logger

router = APIRouter()


# ---------------------------------------------------------------------------
# 请求模型
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str = Field(description="用户名")
    password: str = Field(description="密码")


class RegisterRequest(BaseModel):
    username: str = Field(description="用户名")
    password: str = Field(description="密码")
    display_name: str = Field(default="", description="显示名称")


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    """bcrypt 哈希密码"""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """验证密码"""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def ensure_default_admin():
    """
    确保数据库中存在默认管理员账号 (admin / 123456)。
    如果不存在则自动创建。
    """
    try:
        conn = DatabasePool.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM users WHERE username = %s", ("admin",)
                )
                if cursor.fetchone():
                    return  # 已存在

                # 不存在则创建
                pw_hash = hash_password("123456")
                cursor.execute(
                    "INSERT INTO users (username, password_hash, display_name) VALUES (%s, %s, %s)",
                    ("admin", pw_hash, "管理员"),
                )
                conn.commit()
                logger.info("[Auth] 自动创建默认管理员账号: admin")
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"[Auth] 检查/创建默认管理员账号失败: {e}")


# ---------------------------------------------------------------------------
# API 端点
# ---------------------------------------------------------------------------

@router.post("/api/auth/login")
def api_login(req: LoginRequest):
    """用户登录"""
    try:
        conn = DatabasePool.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id, username, password_hash, display_name FROM users WHERE username = %s",
                    (req.username,),
                )
                row = cursor.fetchone()
                if not row:
                    return JSONResponse({
                        "success": False,
                        "error": "用户名或密码错误",
                    })

                user_id, username, password_hash, display_name = row
                if not verify_password(req.password, password_hash):
                    return JSONResponse({
                        "success": False,
                        "error": "用户名或密码错误",
                    })

                logger.info(f"[Auth] 用户 {username} 登录成功")
                return JSONResponse({
                    "success": True,
                    "user_id": username,  # 使用 username 作为 user_id，与旧会话文件路径兼容
                    "username": username,
                    "display_name": display_name or username,
                })
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"[Auth] 登录异常: {e}")
        return JSONResponse({
            "success": False,
            "error": f"登录失败: {str(e)}",
        })


@router.post("/api/auth/register")
def api_register(req: RegisterRequest):
    """用户注册"""
    if not req.username or len(req.username.strip()) < 2:
        return JSONResponse({
            "success": False,
            "error": "用户名至少 2 个字符",
        })
    if not req.password or len(req.password) < 6:
        return JSONResponse({
            "success": False,
            "error": "密码至少 6 个字符",
        })

    try:
        conn = DatabasePool.get_connection()
        try:
            with conn.cursor() as cursor:
                # 检查用户名是否已存在
                cursor.execute(
                    "SELECT id FROM users WHERE username = %s", (req.username,)
                )
                if cursor.fetchone():
                    return JSONResponse({
                        "success": False,
                        "error": "用户名已存在",
                    })

                # 插入新用户
                pw_hash = hash_password(req.password)
                display = req.display_name or req.username
                cursor.execute(
                    "INSERT INTO users (username, password_hash, display_name) VALUES (%s, %s, %s)",
                    (req.username, pw_hash, display),
                )
                conn.commit()
                user_id = cursor.lastrowid

                logger.info(f"[Auth] 用户 {req.username} 注册成功 (id={user_id})")
                return JSONResponse({
                    "success": True,
                    "user_id": user_id,
                    "username": req.username,
                    "display_name": display,
                })
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"[Auth] 注册异常: {e}")
        return JSONResponse({
            "success": False,
            "error": f"注册失败: {str(e)}",
        })


@router.post("/api/auth/init_default_user")
def api_init_default_user():
    """确保默认管理员账号存在（前端可调用此接口初始化）"""
    ensure_default_admin()
    return JSONResponse({"success": True, "message": "默认账号已检查/创建"})
