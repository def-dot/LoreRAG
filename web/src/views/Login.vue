<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()

const isRegister = ref(false)
const loading = ref(false)

const loginForm = reactive({ username: '', password: '' })
const registerForm = reactive({ username: '', email: '', password: '', confirmPassword: '' })

async function handleLogin() {
  if (!loginForm.username || !loginForm.password) {
    ElMessage.warning('请填写用户名和密码')
    return
  }
  loading.value = true
  try {
    await auth.login(loginForm.username, loginForm.password)
    ElMessage.success('登录成功')
    router.push('/')
  } finally {
    loading.value = false
  }
}

async function handleRegister() {
  if (!registerForm.username || !registerForm.email || !registerForm.password) {
    ElMessage.warning('请填写所有字段')
    return
  }
  if (registerForm.password !== registerForm.confirmPassword) {
    ElMessage.warning('两次密码不一致')
    return
  }
  loading.value = true
  try {
    await auth.register(registerForm.username, registerForm.email, registerForm.password)
    ElMessage.success('注册成功，请登录')
    isRegister.value = false
    loginForm.username = registerForm.username
    loginForm.password = ''
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="brand">
        <div class="brand-mark">L</div>
        <h1 class="brand-name">LoreRAG</h1>
        <p class="brand-sub">企业级 RAG 知识库平台</p>
      </div>

      <!-- 登录 -->
      <el-form v-if="!isRegister" @keyup.enter="handleLogin" class="form">
        <el-form-item>
          <el-input v-model="loginForm.username" placeholder="用户名" size="large" />
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="loginForm.password"
            type="password"
            placeholder="密码"
            size="large"
            show-password
          />
        </el-form-item>
        <el-button
          type="primary"
          size="large"
          :loading="loading"
          class="submit"
          @click="handleLogin"
        >
          登录
        </el-button>
      </el-form>

      <!-- 注册 -->
      <el-form v-else @keyup.enter="handleRegister" class="form">
        <el-form-item>
          <el-input v-model="registerForm.username" placeholder="用户名" size="large" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="registerForm.email" placeholder="邮箱" size="large" />
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="registerForm.password"
            type="password"
            placeholder="密码"
            size="large"
            show-password
          />
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="registerForm.confirmPassword"
            type="password"
            placeholder="确认密码"
            size="large"
            show-password
          />
        </el-form-item>
        <el-button
          type="primary"
          size="large"
          :loading="loading"
          class="submit"
          @click="handleRegister"
        >
          注册
        </el-button>
      </el-form>

      <p class="switch">
        <span v-if="!isRegister"
          >没有账号？<el-link type="primary" :underline="false" @click="isRegister = true"
            >立即注册</el-link
          ></span
        >
        <span v-else
          >已有账号？<el-link type="primary" :underline="false" @click="isRegister = false"
            >返回登录</el-link
          ></span
        >
      </p>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: var(--bg);
}

.login-card {
  width: 380px;
  padding: 40px 36px 32px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  box-shadow: var(--shadow-md);
}

.brand {
  text-align: center;
  margin-bottom: 28px;
}

.brand-mark {
  width: 48px;
  height: 48px;
  margin: 0 auto 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  background: var(--brand);
  color: #fff;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.02em;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
}

.brand-name {
  font-size: 26px;
  font-weight: 700;
  color: var(--ink);
  letter-spacing: -0.01em;
}

.brand-sub {
  margin-top: 6px;
  font-size: 13px;
  color: var(--ink-3);
}

.form :deep(.el-form-item) {
  margin-bottom: 18px;
}

.submit {
  width: 100%;
  margin-top: 4px;
  height: 42px;
}

.switch {
  margin-top: 20px;
  text-align: center;
  font-size: 13px;
  color: var(--ink-3);
}
</style>
