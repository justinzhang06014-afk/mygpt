<!-- src/components/SidebarRooms.vue -->
<template>
  <div class="chat-sidebar w-64 bg-[#f8f9fa] border-r border-[#e5e7eb] flex flex-col shrink-0">
    
    <!-- 🌟 新增：如果當前處於特定 Agent 辦公室，顯示「返回大廳」看板提示 -->
    <div v-if="store.currentAgentId" class="p-3 bg-[#f0f9eb] border-b border-[#e5e7eb] flex items-center justify-between px-4">
      <div class="flex items-center gap-1.5 min-w-0">
        <span class="text-xs">💼</span>
        <span class="text-xs font-bold text-[#67c23a] truncate">辦公室：{{ store.currentAgent?.name }}</span>
      </div>
      <button @click="store.exitToGeneralRag()" class="text-[11px] text-[#9ca3af] hover:text-[#ef5350] underline shrink-0 transition-colors">
        登出返回
      </button>
    </div>

    <!-- 1. 頂部：新增對話房間（維持原本一字不改，會由 Pinia 智慧判定建立一般房或 Agent 房） -->
    <div class="p-4 border-b border-[#e5e7eb]">
      <button @click="emit('create')" class="w-full flex items-center justify-center gap-2 py-2.5 px-4 bg-white border border-[#e5e7eb] hover:border-[#64b5f6] text-[#1f2937] hover:text-[#1e88e5] rounded-xl font-medium shadow-2xs transition-all duration-200 group">
        <span class="text-lg font-bold group-hover:scale-110 transition-transform">+</span>
        <span>新增聊天室</span>
      </button>
    </div>

    <!-- 2. 中間：聊天室清單 (🎯 唯一關鍵改動：將 store.rooms 改為 store.filteredRooms) -->
    <el-scrollbar class="flex-1">
      <div class="p-2 flex flex-col gap-1">
        <!-- 💡 核心過濾線改造：改讀 filteredRooms，自動引導、政治隔離無關房間 -->
        <div v-for="room in store.filteredRooms" :key="room.id" @click="emit('select', room.id)"
             :class="['room-item flex items-center justify-between p-3 rounded-xl cursor-pointer group transition-all duration-150', store.currentRoomId === room.id ? 'bg-[#e3f2fd] text-[#0d47a1] font-medium' : 'text-[#4b5563] hover:bg-[#f3f4f6]']">
          <div class="flex items-center gap-2.5 min-w-0 flex-1">
            <!-- 🌟 視覺識別：如果是 Agent 房或串有 agent_id 就變身機器人 🤖，純 RAG 房維持對話框 💬 -->
            <span class="text-sm shrink-0">
              {{ (room.room_type === 'hermes_agent' || room.room_type === 'Agent' || room.agent_id) ? '🤖' : '💬' }}
            </span>
            <span class="text-sm truncate pr-2">{{ room.title || '新對話聊天室' }}</span>
          </div>
          <div class="flex gap-1 shrink-0 opacity-0 group-hover:opacity-100 transition-all duration-150">
            <button @click.stop="emit('rename', room)" class="p-1 rounded-md text-[#9ca3af] hover:text-[#64b5f6] hover:bg-[#e3f2fd]" title="修改聊天室名稱">✏️</button>
            <button @click.stop="emit('delete', room.id)" class="p-1 rounded-md text-[#9ca3af] hover:text-[#ef5350] hover:bg-[#fde8e8]" title="刪除聊天室">🗑️</button>
          </div>
        </div>
        <div v-if="!store.filteredRooms || store.filteredRooms.length === 0" class="text-center text-xs text-[#9ca3af] py-8">暫無聊天室，請點擊上方新增</div>
      </div>
    </el-scrollbar>

    <!-- 🌟 3. 全新底部進化：專屬大腦助理工作坊（按鈕行為改為：切換右側為 AI 大廳模式） -->
    <div class="p-4 border-t border-[#e5e7eb] bg-white flex flex-col gap-2">
      <div class="text-[11px] font-bold text-[#9ca3af] tracking-wider uppercase pl-1">✨ 專屬大腦助理工作坊</div>
      <button 
        @click="handleToggleMarketMode" 
        :class="['w-full flex items-center justify-center gap-2 py-2.5 px-4 bg-white border border-dashed rounded-xl font-medium shadow-3xs transition-all duration-200 group', store.isAgentMarketMode ? 'border-[#e6a23c] bg-[#fdf6ec] text-[#e6a23c]' : 'border-[#67c23a] hover:bg-[#f0f9eb] text-[#4b5563] hover:text-[#67c23a]']"
      >
        <span class="text-base group-hover:animate-pulse">{{ store.isAgentMarketMode ? '🏠' : '⚡' }}</span>
        <span>{{ store.isAgentMarketMode ? '回到目前聊天' : '進入 AI 專家大廳' }}</span>
      </button>
    </div>
  </div>

  <!-- 💡 💡 提示：原本這裡的 el-dialog 召喚助理彈窗已經被 100% 移到大廳主頁面，這裡完全淨空，不用寫任何彈窗程式碼！ -->
</template>

<script setup>
// 💡 原本宣告的 ref, agentDialogVisible, isSubmitting 變數此處通通不用！

// 1. 接收父元件傳進來的資料狀態 (Pinia Store)
const props = defineProps({ store: Object });

// 2. 拋出事件
const emit = defineEmits(['create', 'select', 'rename', 'delete']);

// 3. 點擊底部按鈕：切換大廳狀態
const handleToggleMarketMode = () => {
  if (props.store.isAgentMarketMode) {
    props.store.isAgentMarketMode = false;
  } else {
    props.store.isAgentMarketMode = true;
    props.store.fetchAgentsAction(); // 前往大廳時，自動觸發 Pinia 拉取最新專家卡片清單！
  }
};
</script>
