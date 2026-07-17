<template>
  <div class="app-layout">
    <header class="app-header">
      <h2>🤖 JChat 智慧化助手</h2>
    </header>
    
    <main class="app-main">
      <!-- 路由出口：ChatRoom.vue 的內容會被渲染在這裡 -->
      <router-view />
    </main>
  </div>
</template>

<style>
/* 全域樣式重設 */
body {
  margin: 0;
  padding: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  background-color: #f0f2f5;
}

.app-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

.app-header {
  background-color: #ffffff;
  padding: 10px 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  z-index: 10;
}

.app-header h2 {
  margin: 0;
  font-size: 1.2rem;
  color: #303133;
}

.app-main {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
</style>
