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
const pageTitle = computed(() => route.meta.title as string)

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
    <!-- ===== Sidebar ===== -->
    <el-aside width="232px" class="aside">
      <div class="brand">
        <div class="brand-mark">
          <span class="brand-initial">L</span>
        </div>
        <div class="brand-text">
          <h2>LoreRAG</h2>
          <span class="brand-tag">企业知识库</span>
        </div>
      </div>

      <nav class="nav-section">
        <el-menu :default-active="activeMenu" router class="menu">
          <el-menu-item v-for="item in menuItems" :key="item.path" :index="item.path">
            <el-icon><component :is="item.icon" /></el-icon>
            <span>{{ item.title }}</span>
          </el-menu-item>
        </el-menu>
      </nav>

      <div class="aside-footer">
        <div class="user-badge">
          <span class="user-avatar">{{ auth.user?.username?.charAt(0)?.toUpperCase() || 'U' }}</span>
          <span class="user-name">{{ auth.user?.username || '用户' }}</span>
        </div>
      </div>
    </el-aside>

    <!-- ===== Right area ===== -->
    <el-container class="right-panel">
      <el-header class="header">
        <div class="header-left">
          <span class="page-title">{{ pageTitle }}</span>
        </div>
        <div class="header-right">
          <el-button :icon="SwitchButton" text class="logout-btn" @click="handleLogout">
            退出登录
          </el-button>
        </div>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
/* ============================================================
   Layout shell — enterprise app chrome
   ============================================================ */

.layout {
  height: 100vh;
  overflow: hidden;
}

/* ---- Sidebar ---- */

.aside {
  background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  box-shadow: 1px 0 0 rgba(15, 23, 42, 0.02);
  transition: box-shadow 0.3s ease;
}

/* Brand block */
.brand {
  height: 64px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 20px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.brand-mark {
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 9px;
  background: linear-gradient(135deg, #2563eb 0%, #4f46e5 100%);
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.25);
  transition: box-shadow 0.3s ease, transform 0.3s ease;
  flex-shrink: 0;
}

.brand-mark:hover {
  box-shadow: 0 4px 14px rgba(37, 99, 235, 0.35);
  transform: scale(1.04);
}

.brand-initial {
  color: #fff;
  font-size: 16px;
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1;
}

.brand-text {
  display: flex;
  flex-direction: column;
  gap: 0px;
  min-width: 0;
}

.brand-text h2 {
  font-size: 17px;
  font-weight: 700;
  color: var(--ink);
  letter-spacing: -0.02em;
  line-height: 1.2;
}

.brand-tag {
  font-size: 11px;
  font-weight: 500;
  color: var(--ink-3);
  letter-spacing: 0.03em;
  text-transform: uppercase;
}

/* Nav section */
.nav-section {
  padding: 16px 16px 0;
  flex: 1;
  overflow-y: auto;
}

.menu {
  border-right: none !important;
  background: transparent;
}

.menu :deep(.el-menu-item) {
  height: 40px;
  line-height: 40px;
  border-radius: 8px;
  margin-bottom: 2px;
  padding-left: 12px !important;
  color: var(--ink-2);
  font-size: 13.5px;
  font-weight: 500;
  transition: all 0.2s ease;
  position: relative;
}

.menu :deep(.el-menu-item .el-icon) {
  font-size: 18px;
  color: var(--ink-3);
  transition: color 0.2s ease;
}

.menu :deep(.el-menu-item:hover) {
  background: var(--surface-2);
  color: var(--ink);
}

.menu :deep(.el-menu-item:hover .el-icon) {
  color: var(--ink-2);
}

.menu :deep(.el-menu-item.is-active) {
  background: var(--brand-soft);
  color: var(--brand);
  font-weight: 600;
}

.menu :deep(.el-menu-item.is-active .el-icon) {
  color: var(--brand);
}

/* Active indicator rail */
.menu :deep(.el-menu-item.is-active)::before {
  content: '';
  position: absolute;
  left: -4px;
  top: 10px;
  bottom: 10px;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: var(--brand);
}

/* Sidebar footer */
.aside-footer {
  padding: 12px 16px;
  border-top: 1px solid var(--border);
  flex-shrink: 0;
}

.user-badge {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  transition: background 0.2s ease;
  cursor: default;
}

.user-badge:hover {
  background: var(--surface-2);
}

.user-avatar {
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 7px;
  background: var(--surface-3);
  color: var(--ink-2);
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}

.user-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--ink-2);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ---- Right panel ---- */

.right-panel {
  flex-direction: column;
  overflow: hidden;
}

/* Header */
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 64px;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 0 28px;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.page-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--ink);
  letter-spacing: -0.01em;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.logout-btn {
  font-size: 13px;
  font-weight: 500;
  color: var(--ink-3);
  transition: color 0.2s ease;
}

.logout-btn:hover {
  color: var(--danger);
}

/* Main content */
.main {
  background: var(--bg);
  overflow-y: auto;
  padding: 24px 28px;
}
</style>
