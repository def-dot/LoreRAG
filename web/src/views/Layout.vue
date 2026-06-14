<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { Folder, ChatDotRound, SwitchButton } from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const activeMenu = computed(() => route.path)

const menuItems = [
  { path: '/knowledge', title: '知识库管理', icon: Folder },
  { path: '/chat', title: '智能问答', icon: ChatDotRound },
]

async function handleLogout() {
  await ElMessageBox.confirm('确定退出登录？', '提示', { type: 'warning' })
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <el-container class="layout">
    <el-aside width="220px" class="aside">
      <div class="brand">
        <div class="brand-mark">L</div>
        <h2>LoreRAG</h2>
      </div>
      <el-menu :default-active="activeMenu" router class="menu">
        <el-menu-item v-for="item in menuItems" :key="item.path" :index="item.path">
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <span class="page-title">{{ route.meta.title }}</span>
        <el-button :icon="SwitchButton" text @click="handleLogout">退出</el-button>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.layout {
  height: 100vh;
}

.aside {
  background: var(--surface);
  border-right: 1px solid var(--border);
}

.brand {
  height: 60px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 20px;
  border-bottom: 1px solid var(--border);
}

.brand-mark {
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: var(--brand);
  color: #fff;
  font-size: 15px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.brand h2 {
  font-size: 18px;
  font-weight: 700;
  color: var(--ink);
  letter-spacing: -0.01em;
}

.menu {
  padding: 8px;
}

.menu :deep(.el-menu-item) {
  height: 42px;
  line-height: 42px;
  border-radius: 6px;
  margin-bottom: 2px;
  color: var(--ink-2);
  font-weight: 500;
}

.menu :deep(.el-menu-item:hover) {
  background: var(--surface-2);
  color: var(--ink);
}

.menu :deep(.el-menu-item.is-active) {
  background: var(--brand-soft);
  color: var(--brand);
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 60px;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 0 24px;
}

.page-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--ink);
}

.main {
  background: var(--bg);
  overflow-y: auto;
}
</style>
