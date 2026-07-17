<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()

const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

onMounted(() => {
  // 如果已經登入過，直接跳轉到主畫面
  const token = localStorage.getItem('auth_token')
  if (token) {
    router.replace('/chat')
  }
})

const handleLogin = async () => {
  error.value = ''

  if (!username.value.trim() || !password.value.trim()) {
    error.value = '請輸入帳號和密碼'
    return
  }

  loading.value = true

  try {
    // ============================================================
    // 🔌 API 連線位置 — 等後端 auth 就緒後開啟
    // 預期後端端點: POST /api/auth/login
    // 請求體: { username: string, password: string }
    // 回應: { token: string, user: { id: number, username: string } }
    // ============================================================
    /*
    const response = await fetch('http://localhost:5000/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username: username.value,
        password: password.value,
      }),
    })

    if (!response.ok) {
      const data = await response.json()
      throw new Error(data.message || '登入失敗')
    }

    const data = await response.json()
    localStorage.setItem('auth_token', data.token)
    localStorage.setItem('user', JSON.stringify(data.user))
    */

    // ⬇️ 模擬登入成功（後端就緒後刪掉這段，改用上方的 API 呼叫）
    await new Promise((resolve) => setTimeout(resolve, 500))
    localStorage.setItem('auth_token', 'mock_token_' + Date.now())
    localStorage.setItem('user', JSON.stringify({ id: 1, username: username.value }))

    router.push('/chat')
  } catch (err: any) {
    error.value = err.message || '登入失敗，請稍後再試'
  } finally {
    loading.value = false
  }
}

const goToRegister = () => {
  router.push('/register')
}

const handleKeyDown = (e: KeyboardEvent) => {
  if (e.key === 'Enter') {
    handleLogin()
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-container">
      <!-- Logo / 標題 -->
      <div class="login-header">
        <div class="logo-icon">🤖</div>
        <h1 class="app-title">JChat 智慧化助手</h1>
        <p class="app-subtitle">登入以繼續使用</p>
      </div>

      <!-- 表單 -->
      <form class="login-form" @submit.prevent="handleLogin">
        <!-- 帳號 -->
        <div class="form-group">
          <label for="username">使用者帳號</label>
          <div class="input-wrapper">
            <span class="input-icon">👤</span>
            <input
              id="username"
              v-model="username"
              type="text"
              placeholder="請輸入您的帳號"
              autocomplete="username"
              @keydown="handleKeyDown"
            />
          </div>
        </div>

        <!-- 密碼 -->
        <div class="form-group">
          <label for="password">使用者密碼</label>
          <div class="input-wrapper">
            <span class="input-icon">🔒</span>
            <input
              id="password"
              v-model="password"
              type="password"
              placeholder="請輸入您的密碼"
              autocomplete="current-password"
              @keydown="handleKeyDown"
            />
          </div>
        </div>

        <!-- 錯誤訊息 -->
        <div v-if="error" class="error-message">
          {{ error }}
        </div>

        <!-- 登入按鈕 -->
        <button type="submit" class="btn-login" :disabled="loading">
          <span v-if="loading" class="loading-spinner"></span>
          {{ loading ? '登入中...' : '登入' }}
        </button>
      </form>

      <!-- 註冊連結 -->
      <div class="register-link">
        <span>還沒有帳號？</span>
        <button class="btn-text" @click="goToRegister">立即註冊</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
  padding: 16px;
}

.login-container {
  width: 100%;
  max-width: 420px;
  background: rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 20px;
  padding: 48px 40px;
  box-shadow: 0 25px 50px rgba(0, 0, 0, 0.3);
}

.login-header {
  text-align: center;
  margin-bottom: 40px;
}

.logo-icon {
  font-size: 56px;
  margin-bottom: 12px;
}

.app-title {
  font-size: 28px;
  font-weight: 700;
  color: #ffffff;
  margin: 0 0 8px 0;
  letter-spacing: -0.5px;
}

.app-subtitle {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.5);
  margin: 0;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.7);
  margin-bottom: 8px;
  letter-spacing: 0.5px;
}

.input-wrapper {
  display: flex;
  align-items: center;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 12px;
  padding: 0 16px;
  transition: all 0.2s ease;
}

.input-wrapper:focus-within {
  border-color: #7c5cfc;
  background: rgba(124, 92, 252, 0.08);
  box-shadow: 0 0 0 3px rgba(124, 92, 252, 0.15);
}

.input-icon {
  font-size: 18px;
  margin-right: 12px;
  flex-shrink: 0;
}

.input-wrapper input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: #ffffff;
  font-size: 15px;
  padding: 14px 0;
}

.input-wrapper input::placeholder {
  color: rgba(255, 255, 255, 0.3);
}

.error-message {
  background: rgba(255, 77, 79, 0.12);
  border: 1px solid rgba(255, 77, 79, 0.3);
  color: #ff4d4f;
  padding: 10px 16px;
  border-radius: 10px;
  font-size: 13px;
  margin-bottom: 20px;
  text-align: center;
}

.btn-login {
  width: 100%;
  padding: 14px;
  background: linear-gradient(135deg, #7c5cfc, #a855f7);
  color: #ffffff;
  border: none;
  border-radius: 12px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  letter-spacing: 0.5px;
  margin-top: 8px;
}

.btn-login:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 8px 25px rgba(124, 92, 252, 0.35);
}

.btn-login:active:not(:disabled) {
  transform: translateY(0);
}

.btn-login:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.loading-spinner {
  display: inline-block;
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #ffffff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
  vertical-align: middle;
  margin-right: 8px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.register-link {
  text-align: center;
  margin-top: 28px;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.5);
}

.btn-text {
  background: none;
  border: none;
  color: #a78bfa;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  margin-left: 4px;
  padding: 0;
  text-decoration: none;
  transition: color 0.2s ease;
}

.btn-text:hover {
  color: #c4b5fd;
  text-decoration: underline;
}
</style>
