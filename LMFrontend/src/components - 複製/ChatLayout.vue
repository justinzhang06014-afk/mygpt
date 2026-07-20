<template>
  <!-- 🚀 指揮官外殼：升級為科技業高質感 SaaS 漸層底色，融入你最愛的淡藍色基因 -->
  <div class="chat-layout-container relative flex w-[96vw] h-[92vh] mx-auto my-4 border border-[#dbeafe] shadow-[0_20px_60px_-15px_rgba(15,23,42,0.12)] rounded-2xl overflow-hidden bg-gradient-to-tr from-[#edf4ff] via-[#f4f9ff] to-[#f8fafc]">
    
    <!-- 左側積木：歷史聊天房間管理 (常駐最左側) -->
    <SidebarRooms 
      :store="chatStore" 
      @create="handleCreateNewChat"
      @select="handleSelectRoom" 
      @rename="handleRenameRoom" 
      @delete="handleDeleteRoom" 
    />

    <!-- 右側動態調度主區域：底色由白改為高級淡藍色 -->
    <div class="chat-main-wrapper flex-1 flex flex-col overflow-hidden bg-[#f3f8fe]">
      
      <!-- ✨ 模式一：專家工作室大廳 -->
      <AgentMarketHall 
        v-if="chatStore.isAgentMarketMode" 
        :chat-store="chatStore" 
      />

      <!-- 💬 模式二：主聊天視窗 + 🛠️ 智能體控制中心 (修正 props 駝峰命名，徹底阻斷編譯快取衝突) -->
      <AgentChatWorkspace 
        v-else 
        :chatStore="chatStore" 
      />

    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue';
import { useChatStore } from '../stores/chat.js';
import { ElMessageBox } from 'element-plus';

// 引入最左側歷史房間元件
import SidebarRooms from './SidebarRooms.vue';

// 🚀 引入核心功能大模組
import AgentMarketHall from './AgentMarketHall.vue';
import AgentChatWorkspace from './AgentChatWorkspace.vue';

// 激活 Pinia 核心大腦儲存庫
const chatStore = useChatStore();

// =========================================================================
// 🔄 生命週期初始化掛載
// =========================================================================
onMounted(async () => {
  // 1. 讀取所有歷史房間
  await chatStore.fetchRoomsAction();
  
  // 2. 終極保險：同步更新檔案清單
  if (chatStore.currentRoomId) {
    await chatStore.fetchCurrentRoomFilesAction(chatStore.currentRoomId);
  }
});

// =========================================================================
// 🛠️ 歷史房間基本管理路由方法
// =========================================================================
const handleCreateNewChat = async () => {
  await chatStore.createNewRoomAction();
};

const handleSelectRoom = async (id) => { 
  await chatStore.switchRoomAction(id); 
};

const handleRenameRoom = (room) => {
  ElMessageBox.prompt('請輸入新名稱：', '改名', { inputValue: room.title }).then(({ value }) => {
    chatStore.updateRoomTitleAction(room.id, value);
  });
};

const handleDeleteRoom = (id) => chatStore.deleteRoomAction(id);
</script>

<style scoped>
/* 科技業高質感 SaaS 外殼：加入更細緻的呼吸過渡與防鋸齒優化 */
.chat-layout-container {
  transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
  backface-visibility: hidden;
  -webkit-font-smoothing: antialiased;
}

/* 微弱科技微光，讓淡藍色外殼層次更立體 */
.chat-layout-container::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 16px;
  pointer-events: none;
  border: 1px solid rgba(255, 255, 255, 0.6);
  z-index: 10;
}
</style>
