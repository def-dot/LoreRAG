import { createRouter, createWebHistory } from 'vue-router'
import Layout from '../views/Layout.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('../views/Login.vue'),
      meta: { guest: true },
    },
    {
      path: '/',
      component: Layout,
      redirect: '/knowledge',
      children: [
        {
          path: 'knowledge',
          name: 'Knowledge',
          component: () => import('../views/Knowledge.vue'),
          meta: { title: '知识库管理' },
        },
        {
          path: 'chat',
          name: 'Chat',
          component: () => import('../views/Chat.vue'),
          meta: { title: '智能问答' },
        },
      ],
    },
  ],
})

// 路由守卫
router.beforeEach((to) => {
  const token = localStorage.getItem('access_token')
  if (!to.meta.guest && !token) {
    return { path: '/login' }
  }
  if (to.meta.guest && token) {
    return { path: '/' }
  }
})

export default router
