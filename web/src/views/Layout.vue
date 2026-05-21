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
    <!-- 侧边栏 -->
    <el-aside width="220px" class="aside">
      <div class="logo">
        <h2>LoreRAG</h2>
      </div>
      <el-menu :default-active="activeMenu" router class="menu" background-color="transparent" text-color="#ccc"
        active-text-color="#409eff">
        <el-menu-item v-for="item in menuItems" :key="item.path" :index="item.path">
          <el-icon>
            <component :is="item.icon" />
          </el-icon>
          <span>{{ item.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <!-- 主内容 -->
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
  background: #1a1a2e;
  border-right: 1px solid rgba(255, 255, 255, 0.06);
}

.logo {
  padding: 20px 24px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.logo h2 {
  color: #e0e0e0;
  font-size: 22px;
  margin: 0;
}

.menu {
  border-right: none;
  margin-top: 8px;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #eee;
}

.page-title {
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.main {
  background: #f5f7fa;
  overflow-y: auto;
}
</style>
