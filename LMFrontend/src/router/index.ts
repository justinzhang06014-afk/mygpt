import { createRouter, createWebHistory } from 'vue-router'
import ChatRoom from '@/components/ChatRoom.vue' // 💡 確保路徑指向您的對話元件
import Login from '@/components/Login.vue'
// import ChatLayout from '@/components/ChatLayout.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: Login // 💡 讓首頁直接顯示聊天室
    }
  ]
})

export default router
