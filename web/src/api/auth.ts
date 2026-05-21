import request from './request'

export interface LoginParams {
  username: string
  password: string
}

export interface RegisterParams {
  username: string
  email: string
  password: string
  confirm_password: string
}

export interface TokenData {
  access_token: string
  refresh_token: string
  token_type: string
}

// 登录 — OAuth2 form 格式
export function login(params: LoginParams) {
  const form = new URLSearchParams()
  form.append('username', params.username)
  form.append('password', params.password)
  return request.post<{ code: number; msg: string; data: TokenData }>('/auth/login', form)
}

// 注册
export function register(params: RegisterParams) {
  return request.post<{ code: number; msg: string; data: { id: number; username: string } }>(
    '/auth/register',
    params,
  )
}
