"""认证路由 - 注册 / 登录"""

from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlmodel import select

from app.core.deps import CurrentUser, OAuth2Form, SessionDep
from app.core.logging import get_logger
from app.core.response import UnifiedResponseRoute
from app.core.security import (
    DUMMY_HASHED_PASSWORD,
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_access_token,
    hash_password,
    verify_and_update_password,
    verify_password,
    verify_password_reset_token,
)
from app.models.user import User, UserCreate, UserOut
from app.schemas.schemas import (
    PasswordChangeRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    Token,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["认证"], route_class=UnifiedResponseRoute)


def send_welcome_email(email: str, username: str) -> None:
    """后台任务：发送欢迎邮件"""
    logger.info("Welcome email sent to %s for user %s", email, username)


def send_password_reset_email(email: str, token: str) -> None:
    """后台任务：发送密码重置邮件"""
    logger.info("Password reset email sent to %s, token=%s...", email, token[:8])


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
)
async def register(user_in: UserCreate, background_tasks: BackgroundTasks, db: SessionDep) -> Any:
    """注册新用户"""
    result = await db.exec(select(User).where(User.username == user_in.username))
    if result.first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    result = await db.exec(select(User).where(User.email == user_in.email))
    if result.first():
        raise HTTPException(status_code=400, detail="邮箱已注册")

    user = User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    background_tasks.add_task(send_welcome_email, user.email, user.username)
    logger.info("User registered: %s", user.username)
    return user


@router.post("/login", response_model=Token)
async def login(form: OAuth2Form, db: SessionDep) -> Any:
    """登录获取 JWT Token - 支持用户名或邮箱登录（OAuth2 兼容）"""
    result = await db.exec(select(User).where((User.username == form.username) | (User.email == form.username)))
    user = result.first()

    # 无论用户是否存在都执行一次哈希验证，防止通过响应时间枚举用户名
    password_hash = user.hashed_password if user else DUMMY_HASHED_PASSWORD
    password_ok, updated_hash = verify_and_update_password(form.password, password_hash)
    if not user or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户或密码错误",
        )

    # 哈希算法过旧时自动升级
    if updated_hash:
        user.hashed_password = updated_hash
        db.add(user)
        await db.commit()
    access_token = create_access_token(data={"sub": user.username})
    refresh_token = create_refresh_token(data={"sub": user.username})
    logger.info("User logged in: %s", user.username)
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=Token)
async def refresh(body: RefreshTokenRequest) -> Any:
    """用 refresh token 换取新的 access token 和 refresh token"""
    payload = decode_access_token(body.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的 refresh token")

    username: str | None = payload.get("sub")
    if username is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的 refresh token")

    access_token = create_access_token(data={"sub": username})
    new_rt = create_refresh_token(data={"sub": username})
    return Token(access_token=access_token, refresh_token=new_rt)


@router.post("/password-reset")
async def request_password_reset(body: PasswordResetRequest, background_tasks: BackgroundTasks, db: SessionDep) -> Any:
    """申请密码重置 — 无论邮箱是否存在都返回相同响应，防止枚举"""
    result = await db.exec(select(User).where(User.email == body.email))
    user = result.first()

    if user:
        token = create_password_reset_token(user.email)
        background_tasks.add_task(send_password_reset_email, user.email, token)
        logger.info("Password reset requested for %s", user.email)

    # 邮箱不存在也返回成功，不泄露信息
    return None


@router.post("/password-reset/confirm")
async def confirm_password_reset(body: PasswordResetConfirm, db: SessionDep) -> Any:
    """确认密码重置 — 用 token 设置新密码"""
    email = verify_password_reset_token(body.token)

    result = await db.exec(select(User).where(User.email == email))
    user = result.first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")

    user.hashed_password = hash_password(body.new_password)
    db.add(user)
    await db.commit()
    logger.info("Password reset confirmed for %s", user.email)
    return None


@router.patch("/change-password")
async def change_password(body: PasswordChangeRequest, user: CurrentUser, db: SessionDep) -> Any:
    """修改密码 — 需登录，验证旧密码后设置新密码"""
    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="当前密码错误")

    user.hashed_password = hash_password(body.new_password)
    db.add(user)
    await db.commit()
    logger.info("Password changed for %s", user.username)
    return None
