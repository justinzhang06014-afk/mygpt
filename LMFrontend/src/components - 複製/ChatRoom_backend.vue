<template>
  <div class="chat-layout-container flex w-full h-[calc(100vh-40px)] max-w-6xl mx-auto my-5 border border-[#e5e7eb] shadow-xl rounded-2xl overflow-hidden bg-[#ffffff]">
    
    <div class="chat-sidebar w-64 bg-[#f8f9fa] border-r border-[#e5e7eb] flex flex-col shrink-0">
      <div class="p-4 border-b border-[#e5e7eb]">
        <button 
          @click="handleCreateNewChat"
          class="w-full flex items-center justify-center gap-2 py-2.5 px-4 bg-white border border-[#e5e7eb] hover:border-[#64b5f6] text-[#1f2937] hover:text-[#1e88e5] rounded-xl font-medium shadow-2xs transition-all duration-200 group"
        >
          <span class="text-lg font-bold group-hover:scale-110 transition-transform">+</span>
          <span>新增聊天室</span>
        </button>
      </div>

      <el-scrollbar class="flex-1">
        <div class="p-2 flex flex-col gap-1">
          <div 
            v-for="room in chatStore.rooms" 
            :key="room.id"
            @click="handleSelectRoom(room.id)"
            :class="[
              'room-item flex items-center justify-between p-3 rounded-xl cursor-pointer group transition-all duration-150',
              chatStore.currentRoomId === room.id ? 'bg-[#e3f2fd] text-[#0d47a1] font-medium' : 'text-[#4b5563] hover:bg-[#f3f4f6]'
            ]"
          >
            <div class="flex items-center gap-2.5 min-w-0 flex-1">
              <span class="text-sm shrink-0">💬</span>
              <span class="text-sm truncate pr-2">{{ room.title || '新對話聊天室' }}</span>
            </div>
            <!-- ✏️ 新增修改名稱按鈕 -->
            <button 
              @click.stop="handleRenameRoom(room)"
              class="p-1 rounded-md text-[#9ca3af] hover:text-[#64b5f6] hover:bg-[#e3f2fd]"
              title="修改聊天室名稱"
            >
              ✏️
            </button>
            <button 
              @click.stop="handleDeleteRoom(room.id)"
              class="opacity-0 group-hover:opacity-100 p-1 rounded-md text-[#9ca3af] hover:text-[#ef5350] hover:bg-[#fde8e8] transition-all duration-150 shrink-0"
              title="刪除聊天室"
            >
              🗑️
            </button>
          </div>

          <div v-if="!chatStore.rooms || chatStore.rooms.length === 0" class="text-center text-xs text-[#9ca3af] py-8">
            暫無聊天室，請點擊上方新增
          </div>
        </div>
      </el-scrollbar>
    </div>

    <div class="chat-main-wrapper flex-1 flex flex-col overflow-hidden bg-white">
      
      <div class="chat-header py-4 px-6 bg-white border-b border-[#f3f4f6] flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="w-3 h-3 rounded-full bg-[#64b5f6] animate-pulse"></div>
          <h1 class="text-lg font-semibold text-[#1f2937] tracking-wide">
            {{ currentRoomTitle || 'Qwen AI 智慧聯網助理' }}
          </h1>
        </div>
        <span class="text-xs text-[#9ca3af] bg-[#f3f4f6] px-3 py-1 rounded-full font-medium">即時搜尋啟用版</span>
      </div>

      <el-scrollbar class="chat-window flex-1 bg-[#f9f9f9]" ref="scrollbarRef">
        <div v-if="!chatStore.currentRoomId" class="h-full flex flex-col items-center justify-center text-[#9ca3af] gap-2 py-20">
          <span class="text-4xl">👋</span>
          <p class="text-sm">歡迎！請在左側選擇或建立一個聊天室開始對話。</p>
        </div>

        <div v-else class="chat-content-inner p-6 max-w-3xl mx-auto flex flex-col gap-6">
          <div v-for="(msg, index) in chatStore.messages" :key="index" 
               :class="['message-row flex w-full gap-4 group', msg.role === 'user' ? 'flex-row-reverse' : 'flex-row']">
            
            <div :class="['avatar-box w-9 h-9 rounded-xl flex items-center justify-center text-base shadow-sm select-none shrink-0', 
                          msg.role === 'user' ? 'bg-[#bbdefb]' : 'bg-white border border-[#e5e7eb]']">
              {{ msg.role === 'user' ? '👤' : '🤖' }}
            </div>
            
            <div :class="['flex flex-col max-w-[72%]', msg.role === 'user' ? 'items-end' : 'items-start']">
              
              <div v-if="msg.role === 'user' && editingId === msg.id" class="edit-card w-72 sm:w-96 bg-white p-3 rounded-xl shadow-lg border border-[#e5e7eb] flex flex-col gap-3">
                <el-input v-model="editText" type="textarea" :rows="2" resize="none" class="modern-textarea" />
                <div class="flex justify-between items-center">
                  <el-checkbox v-model="editWebSearch" size="small">🌐 聯網搜尋</el-checkbox>
                  <div class="flex gap-2">
                    <el-button size="small" class="!rounded-md" @click="cancelEdit">取消</el-button>
                    <el-button size="small" type="primary" class="!rounded-md !bg-[#64b5f6] !border-[#64b5f6]" :loading="chatStore.isLoading" @click="submitEdit(msg.id)">儲存送出</el-button>
                  </div>
                </div>
              </div>

              <div v-else class="flex flex-col gap-2 w-full">
                <div v-if="msg.role === 'assistant' && msg.searchSources && msg.searchSources.length > 0" class="w-full flex flex-col gap-1.5 mb-1">
                  <div class="text-xs text-[#9ca3af] flex items-center gap-1 font-medium select-none">
                    <span>🔍 已參考 Google 搜尋到的即時資料：</span>
                  </div>
                  <div class="flex gap-2 overflow-x-auto pb-1 max-w-full scrollbar-thin">
                    <a v-for="(src, sIdx) in msg.searchSources" :key="sIdx" :href="src.link" target="_blank"
                       class="flex-shrink-0 w-44 bg-white hover:bg-[#f4faff] border border-[#e5e7eb] hover:border-[#90caf9] p-2 rounded-xl text-left shadow-2xs transition-all duration-200 group/card"
                    >
                      <h4 class="text-xs font-semibold text-[#374151] truncate group-hover/card:text-[#1e88e5]">{{ src.title }}</h4>
                      <p class="text-[10px] text-[#9ca3af] truncate mt-0.5">{{ src.snippet }}</p>
                    </a>
                  </div>
                </div>

                <div :class="['bubble px-4 py-3 rounded-2xl shadow-sm border text-[15px] leading-relaxed transition-all duration-200', msg.role === 'user' ? 'bg-[#e3f2fd] border-[#c4e1f6] text-[#0d47a1] rounded-tr-none hover:shadow' : 'bg-white border-[#e5e7eb] text-[#1f2937] rounded-tl-none hover:shadow']">
                  <p class="message-text m-0 white-space-pre-wrap">{{ msg.content }}</p>
                </div>
              </div>
              
              <div v-if="msg.role === 'user' && msg.id && editingId !== msg.id" class="action-group flex gap-3 mt-1.5 px-1 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                <button class="text-xs text-[#9ca3af] hover:text-[#42a5f5] transition-colors" @click="startEdit(msg)">編輯</button>
                <span class="text-[10px] text-[#e5e7eb] self-center">|</span>
                <button class="text-xs text-[#9ca3af] hover:text-[#ef5350] transition-colors" @click="handleRetract(msg.id)">收回</button>
              </div>
            </div>
          </div>

          <div v-if="chatStore.isLoading" class="message-row flex w-full gap-4 flex-row">
            <div class="w-9 h-9 rounded-xl flex items-center justify-center text-base shadow-sm bg-white border border-[#e5e7eb] shrink-0">🤖</div>
            <div class="bubble px-4 py-3 rounded-2xl rounded-tl-none shadow-sm border bg-white border-[#e5e7eb] text-[15px] text-[#6b7280] flex items-center gap-2">
              <el-icon class="is-loading text-[#64b5f6]"><Loading /></el-icon> 
              <span class="tracking-wide animate-pulse">Qwen 正在連網並思考中...</span>
            </div>
          </div>
        </div>
      </el-scrollbar>

      <div class="input-container-box p-4 bg-white border-t border-[#f3f4f6]">
        <div class="max-w-3xl mx-auto relative border border-[#e5e7eb] focus-within:border-[#64b5f6] focus-within:ring-2 focus-within:ring-[#e3f2fd] rounded-xl px-3 py-2 transition-all bg-white shadow-sm">
          <el-input
            v-model="userMessage"
            placeholder="傳送訊息給啟用聯網的 Qwen..."
            type="textarea"
            :rows="2"
            resize="none"
            :disabled="chatStore.isLoading || !chatStore.currentRoomId"
            class="main-chat-input"
            @keydown.enter.prevent="handleSend"
          />
          <div class="flex justify-between items-center mt-2 pt-1 border-t border-[#f9fafb]">
            <div class="flex items-center gap-1.5 select-none">
              <el-switch v-model="isWebSearchActive" :disabled="!chatStore.currentRoomId" active-text="搜尋網路" inline-prompt style="--el-switch-on-color: #64b5f6;" />
            </div>
            
            <div class="flex items-center">
              <span class="text-xs text-[#9ca3af] mr-4 hidden sm:inline">按 Enter 傳送訊息</span>
              <el-button 
                type="primary" 
                class="!rounded-lg !px-5 !bg-[#64b5f6] !border-[#64b5f6] hover:!bg-[#42a5f5] hover:!border-[#42a5f5] transition-colors"
                :loading="chatStore.isLoading" 
                :disabled="!chatStore.currentRoomId"
                @click="handleSend"
              >
                傳送
              </el-button>
            </div>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, computed } from 'vue';
import { useChatStore } from '../stores/chat';
import { Loading } from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox } from 'element-plus';

// 狀態大腦初始化
const chatStore = useChatStore();
const userMessage = ref('');
const scrollbarRef = ref(null);

// 💡 響應式變數：控制主輸入框與編輯框的聯網狀態
const isWebSearchActive = ref(false); // 預設關閉一般對話，點開變天藍色啟動 Google
const editingId = ref(null); 
const editText = ref('');    
const editWebSearch = ref(false); // 編輯專用聯網狀態

// =========================================================================
// 💡 多聊天室（一對多）聯動與控制
// =========================================================================

// 計算屬性：即時動態獲取當前聊天室的標題名稱，供 Header 顯示
const currentRoomTitle = computed(() => {
  if (!chatStore.rooms || !chatStore.currentRoomId) return 'Qwen AI 智慧聯網助理';
  const activeRoom = chatStore.rooms.find(r => r.id === chatStore.currentRoomId);
  return activeRoom ? activeRoom.title : '新對話聊天室';
});

// 🚀 功能 1：點擊「➕ 新增聊天室」按鈕
const handleCreateNewChat = async () => {
  try {
    await chatStore.createNewRoomAction();
    userMessage.value = ''; // 清空目前的輸入框
    cancelEdit();
  } catch (err) {
    console.error("建立聊天室失敗:", err);
    ElMessage.error("建立聊天室失敗");
  }
};

// 🚀 功能 2：點擊切換聊天室
const handleSelectRoom = async (roomId) => {
  if (chatStore.isLoading) return; // AI 還在思考中時，禁止切換房間
  cancelEdit();
  try {
    await chatStore.switchRoomAction(roomId);
    scrollToBottom();
  } catch (err) {
    console.error("切換聊天室失敗:", err);
    ElMessage.error("載入聊天歷史失敗");
  }
};

// 🚀 功能 3：點擊側邊欄刪除聊天室 🗑️
const handleDeleteRoom = (roomId) => {
  ElMessageBox.confirm(
    '確定要刪除這個聊天室嗎？歷史訊息將會被永久刪除。',
    '警告',
    { confirmButtonText: '確定刪除', cancelButtonText: '取消', type: 'danger' }
  ).then(async () => {
    try {
      await chatStore.deleteRoomAction(roomId);
      ElMessage({ type: 'success', message: '聊天室已成功刪除' });
    } catch (err) {
      console.error("刪除聊天室失敗:", err);
      ElMessage.error("刪除聊天室失敗");
    }
  }).catch(() => {});
};
// 🚀 新增：點擊修改聊天室名稱的互動視窗
const handleRenameRoom = (room) => {
  ElMessageBox.prompt('請輸入新的聊天室名稱：', '修改名稱', {
    confirmButtonText: '確定',
    cancelButtonText: '取消',
    inputValue: room.title, // 預設帶入原本的房間名稱
    inputPattern: /\S+/,    // 防呆：不能輸入全空白
    inputErrorMessage: '聊天室名稱不能為空'
  }).then(async ({ value }) => {
    const success = await chatStore.updateRoomTitleAction(room.id, value);
    if (success) {
      ElMessage({ type: 'success', message: '聊天室名稱已成功變更' });
    } else {
      ElMessage.error('修改名稱失敗');
    }
  }).catch(() => {});
};
// =========================================================================
// 💡 訊息發送、編輯與撤回
// =========================================================================

// 傳送訊息
const handleSend = async () => {
  // 防呆：沒字、讀取中、或是根本沒開房間時，不觸發
  if (!userMessage.value.trim() || chatStore.isLoading || !chatStore.currentRoomId) return;
  
  const textToSend = userMessage.value.trim();
  userMessage.value = ''; 
  
  try {
    // 呼叫 Store 發送，傳入訊息內容、當前聊天室 ID、聯網設定
    await chatStore.sendMessageAction({
      roomId: chatStore.currentRoomId,
      content: textToSend,
      isWebSearch: isWebSearchActive.value
    });
    scrollToBottom(); 
  } catch (err) {
    console.error("發送訊息失敗:", err);
  }
};

// 收回訊息
const handleRetract = (messageId) => {
  ElMessageBox.confirm(
    '確定要收回此訊息嗎？',
    '提示',
    { confirmButtonText: '確定收回', cancelButtonText: '取消', type: 'warning' }
  ).then(async () => {
    const success = await chatStore.deleteMessage(messageId);
    if (success) ElMessage({ type: 'success', message: '訊息已成功收回' });
  }).catch(() => {});
};

// 開始編輯問題
const startEdit = (msg) => {
  editingId.value = msg.id;     
  editText.value = msg.content; 
  editWebSearch.value = false; // 預設編輯不開搜尋
};

// 取消編輯
const cancelEdit = () => {
  editingId.value = null;
  editText.value = '';
};

// 儲存並送出編輯後的問題
const submitEdit = async (messageId) => {
  if (!editText.value.trim() || chatStore.isLoading) return;

  const success = await chatStore.updateMessage(messageId, editText.value, editWebSearch.value);
  if (success) {
    ElMessage({ type: 'success', message: '問題已成功修改，AI 已聯網重製回答' });
    editingId.value = null; 
    editText.value = '';
    scrollToBottom();
  }
};

// 滾動條自動探底
const scrollToBottom = () => {
  nextTick(() => {
    if (scrollbarRef.value) {
      setTimeout(() => {
        scrollbarRef.value.setScrollTop(999999);
      }, 50);
    }
  });
};

// 初始化：開機自動撈取該使用者的所有聊天室清單
onMounted(async () => {
  try {
    await chatStore.fetchRoomsAction();
    scrollToBottom();
  } catch (err) {
    console.error("初始化聊天室清單失敗:", err);
  }
});
</script>


<style scoped>
:deep(.main-chat-input .el-textarea__inner) {
  border: none !important;
  box-shadow: none !important;
  padding: 5px 0 !important;
  background: transparent !important;
  font-size: 15px;
  color: #1f2937;
}
:deep(.modern-textarea .el-textarea__inner) {
  border: 1px solid #e5e7eb !important;
  box-shadow: none !important;
  border-radius: 8px !important;
  font-size: 14px;
}
:deep(.modern-textarea .el-textarea__inner:focus) {
  border-color: #64b5f6 !important;
}
.white-space-pre-wrap {
  white-space: pre-wrap;
}
/* 讓水平滑動條保持極度簡潔精緻 */
.scrollbar-thin::-webkit-scrollbar {
  height: 4px;
}
.scrollbar-thin::-webkit-scrollbar-thumb {
  background: #e5e7eb;
  border-radius: 10px;
}
</style>
