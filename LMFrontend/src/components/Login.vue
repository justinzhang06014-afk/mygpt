<template>
  <div class="auth-container">
    
    <!-- 💡 3. 如果尚未登入，顯示登入或註冊畫面 -->
    <div v-if="!isLoggedIn">
      
      <!-- ==================== 登入畫面 ==================== -->
      <div v-if="currentScreen === 'login'" class="auth-card animate-fade">
        <h2 class="auth-title">HMS平台系統登入</h2>
        
        <div class="input-group">
          <label>使用者帳號</label>
          <input v-model="loginForm.username" type="text" placeholder="請輸入帳號" />
        </div>
        
        <div class="input-group">
          <label>使用者密碼</label>
          <input v-model="loginForm.password" type="password" placeholder="請輸入密碼" />
        </div>
        
        <button @click="handleLogin" class="btn btn-primary">登入系統</button>
        
        <div class="auth-footer">
          沒有帳號？ <a @click.prevent="currentScreen = 'register'" href="#">立即註冊</a>
        </div>
      </div>

      <!-- ==================== 註冊畫面 ==================== -->
      <div v-else-if="currentScreen === 'register'" class="auth-card animate-fade">
        <h2 class="auth-title">新使用者註冊</h2>
        
        <div class="input-group">
          <label>使用者帳號</label>
          <input v-model="registerForm.username" type="text" placeholder="請設定新帳號" />
        </div>
        
        <div class="input-group">
          <label>密碼設定</label>
          <input v-model="registerForm.password" type="password" placeholder="請設定新密碼" />
        </div>
        
        <div class="btn-group">
          <button @click="handleRegister" class="btn btn-success">確認註冊</button>
          <button @click="clearRegisterForm" class="btn btn-light">清除內容</button>
        </div>
        
        <button @click="currentScreen = 'login'" class="btn btn-link">返回登入頁面</button>
      </div>

    </div>

    <!-- 💡 4. 登入成功後，直接換成 ChatRoom 巨幕 -->
    <ChatRoom v-else />

  </div>
</template>


<script setup>
import { ref, onMounted, reactive } from 'vue';
import { useChatStore } from '../stores/chat';
// 💡 1. 正式匯入你的 ChatRoom 元件（請根據你實際的檔案路徑調整，通常在同層或 components 資料夾）
import ChatRoom from './ChatRoom.vue'; 
import axios from 'axios'; // 🎯 直接引入官方的 axios 套件


const isLoggedIn = ref(false);
const currentScreen = ref('login'); // 'login' | 'register'

// 登入表單資料
const loginForm = reactive({
  username: '',
  password: ''
});

// 註冊表單資料
const registerForm = reactive({
  username: '',
  password: ''
});

const emit = defineEmits(['login-success']);
const chatStore = useChatStore();

// 處理登入
// 處理登入
const handleLogin = async () => {
  if (!loginForm.username || !loginForm.password) {
    alert('請填寫帳號與密碼！');
    return;
  }

  // 🎯 確保這裡傳進去的是 loginForm 的實際數值
  const isVerified = await chatStore.loginUserAction(loginForm.username, loginForm.password);

  if (isVerified) {
    isLoggedIn.value = true;
    emit('login-success');
  } else {
    loginForm.password = '';
  }
};



// 處理確認註冊
// 處理確認註冊
// 處理確認註冊
const handleRegister = async () => {
  // 🛡️ 1. 防呆檢查（維持你原本的優秀防線）
  if (!registerForm.username || !registerForm.password) {
    alert('請輸入要註冊的帳號與密碼！');
    return;
  }
  
  try {
    // 🎯 終極修正：必須從 registerForm 物件裡面把值拔出來傳出去！
    // 並且 Key 值必須精確對應到 C# 後端 AuthDto 的 Username 與 Password（注意大寫對齊）
    await axios.post('/api/auth/register', {
      Username: registerForm.username.trim(), // 👈 這裡才是真正把畫面輸入的名字傳出去！
      Password: registerForm.password         // 👈 這裡才是真正把畫面輸入的密碼傳出去！
    });

    alert(`帳號 [${registerForm.username}] 註冊成功！將為您返回登入頁面。`);
    clearRegisterForm();
    currentScreen.value = 'login';
  } catch (err) {
    // 顯示最真實的後端報錯，不再瞎猜
    const errorMsg = err.response?.data?.message || err.message;
    alert("系統回報訊息：" + errorMsg);
  }
};




const clearRegisterForm = () => {
  registerForm.username = '';
  registerForm.password = '';
};

// 初始化檢查
// onMounted(() => {
//   if (isLoggedIn.value || chatStore.currentUserId) {
//     isLoggedIn.value = true;
//     return;
//   }

//   const savedUser = localStorage.getItem('CORE_CURRENT_USER_ID');
//   if (savedUser) {
//     chatStore.currentUserId = savedUser; 
//     isLoggedIn.value = true;             
//   }
// });
</script>

<style scoped>
/* 全域淡藍色優雅背景 */
.auth-container {
  width: 100vw;
  height: 100vh;
  background: linear-gradient(135deg, #e0f2fe 0%, #bae6fd 100%);
  display: flex;
  justify-content: center;
  align-items: center;
  font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

/* 置中精美白色卡片框框 */
.auth-card {
  background: #ffffff;
  padding: 2.5rem;
  border-radius: 16px;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.05);
  width: 100%;
  max-width: 400px;
  box-sizing: border-box;
}

.auth-title {
  color: #0369a1;
  text-align: center;
  margin-bottom: 2rem;
  font-size: 1.5rem;
  font-weight: 600;
}

/* 輸入框排版 */
.input-group {
  margin-bottom: 1.25rem;
  display: flex;
  flex-direction: column;
}

.input-group label {
  font-size: 0.875rem;
  color: #475569;
  margin-bottom: 0.5rem;
  font-weight: 500;
}

.input-group input {
  padding: 0.75rem 1rem;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-size: 1rem;
  transition: all 0.2s ease;
  outline: none;
}

.input-group input:focus {
  border-color: #0284c7;
  box-shadow: 0 0 0 3px rgba(2, 132, 199, 0.15);
}

/* 按鈕樣式規範 */
.btn {
  width: 100%;
  padding: 0.75rem;
  border-radius: 8px;
  font-size: 1rem;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: background-color 0.2s ease;
}

.btn-primary {
  background-color: #0284c7;
  color: white;
}

.btn-primary:hover {
  background-color: #0369a1;
}

.btn-success {
  background-color: #10b981;
  color: white;
}

.btn-success:hover {
  background-color: #059669;
}

.btn-light {
  background-color: #f1f5f9;
  color: #334155;
  border: 1px solid #cbd5e1;
}

.btn-light:hover {
  background-color: #e2e8f0;
}

.btn-link {
  background: none;
  color: #64748b;
  text-decoration: underline;
  margin-top: 1rem;
  font-size: 0.875rem;
}

.btn-link:hover {
  color: #334155;
}

.btn-sm {
  width: auto;
  padding: 0.4rem 1rem;
  font-size: 0.875rem;
}

.btn-danger {
  background-color: #ef4444;
  color: white;
}

.btn-danger:hover {
  background-color: #dc2626;
}

/* 按鈕並排組 */
.btn-group {
  display: flex;
  gap: 1rem;
  margin-bottom: 0.5rem;
}

/* 頁尾連結區 */
.auth-footer {
  text-align: center;
  margin-top: 1.5rem;
  font-size: 0.875rem;
  color: #64748b;
}

.auth-footer a {
  color: #0284c7;
  text-decoration: none;
  font-weight: 500;
}

.auth-footer a:hover {
  text-decoration: underline;
}

/* 暫時的聊天室歡迎框 */
.chatroom-main {
  background: #ffffff;
  padding: 3rem;
  border-radius: 16px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.08);
  text-align: center;
  max-width: 500px;
}

.welcome-box h2 {
  color: #0f172a;
  margin-bottom: 1rem;
}

.status-hint {
  color: #10b981;
  font-weight: 500;
  background-color: #ecfdf5;
  padding: 0.75rem;
  border-radius: 8px;
  margin: 1.5rem 0;
}

/* 微漸變動態特效 */
.animate-fade {
  animation: fadeIn 0.3s ease-in-out;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
