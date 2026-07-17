import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css' // 引入樣式
import App from './App.vue' //這裡報錯正常 VS Code 外掛衝突 用 (Disable)：Vetur 外掛 安裝 (Install)：Vue - Official 外掛
import router from './router'
import './tailwind.css'
const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(ElementPlus) // 啟用 Element Plus
app.mount('#app')
