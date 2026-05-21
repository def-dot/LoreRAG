import { defineStore } from 'pinia'
import { ref } from 'vue'
import { login as loginApi, register as registerApi } from '../api/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('access_token') || '')
  const isLoggedIn = ref(!!token.value)

  async function login(username: string, password: string) {
    const res = await loginApi({ username, password })
    const data = res.data.data
    token.value = data.access_token
    localStorage.setItem('access_token', data.access_token)
    isLoggedIn.value = true
  }

  async function register(username: string, email: string, password: string) {
    await registerApi({ username, email, password, confirm_password: password })
  }

  function logout() {
    token.value = ''
    isLoggedIn.value = false
    localStorage.removeItem('access_token')
  }

  return { token, isLoggedIn, login, register, logout }
})
