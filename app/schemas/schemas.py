"""Pydantic 请求/响应 Schema"""

from pydantic import BaseModel, Field


class Page[T](BaseModel):
    """分页数据"""

    items: list[T] = Field(description="数据列表")
    total: int = Field(description="总数量")


# ---------- Auth ----------
class Token(BaseModel):
    """JWT Token"""

    access_token: str = Field(description="访问令牌")
    refresh_token: str = Field(description="刷新令牌")
    token_type: str = Field(default="bearer", description="令牌类型")


class TokenData(BaseModel):
    username: str | None = None


class RefreshTokenRequest(BaseModel):
    """刷新令牌请求"""

    refresh_token: str = Field(description="刷新令牌")


class PasswordResetRequest(BaseModel):
    """密码重置请求（忘记密码）"""

    email: str = Field(description="注册邮箱")


class PasswordResetConfirm(BaseModel):
    """密码重置确认"""

    token: str = Field(description="重置令牌")
    new_password: str = Field(min_length=6, description="新密码")


class PasswordChangeRequest(BaseModel):
    """修改密码"""

    current_password: str = Field(description="当前密码")
    new_password: str = Field(min_length=6, description="新密码")
