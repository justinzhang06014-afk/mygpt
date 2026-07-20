<!-- src/components/ChatInputArea.vue -->
<template>
  <div class="input-container-box p-4 bg-white border-t border-[#f3f4f6]">
    <div class="max-w-3xl mx-auto relative border border-[#e5e7eb] focus-within:border-[#64b5f6] focus-within:ring-2 focus-within:ring-[#e3f2fd] rounded-xl px-3 py-2 transition-all bg-white shadow-sm">
      
      <!-- 💡 RAG 升級完全體：顯示知識庫文件，並加入實體 ✕ 刪除按鈕 -->
      <div v-if="uploadedFiles && uploadedFiles.length > 0" class="flex gap-2 flex-wrap mb-2 pb-1.5 border-b border-[#f3f4f6]">
        <span 
          v-for="file in uploadedFiles" 
          :key="file.id || (file.file_name || file.fileName)" 
          class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-[#e8f5e9] text-[#2e7d32] border border-[#a5d6a7]"
        >
          <!-- 💡 雙重相容後端欄位：file.file_name 或 file.fileName -->
          <span>📄 {{ file.file_name || file.fileName }}</span>
          <small class="text-[#81c784]">(RAG 已就緒)</small>
          
          <!-- 🗑️ 點擊發動 RAG 物理蒸發 -->
          <button 
            @click="handleRemoveFile(file.file_name || file.fileName)" 
            class="ml-1 text-[#a5d6a7] hover:text-red-500 font-bold focus:outline-none transition-colors duration-150 cursor-pointer text-[10px]"
            title="將此文件移出當前知識庫"
          >
            ✕
          </button>
        </span>
      </div>

      <el-input
        v-model="messageText"
        placeholder="傳送訊息給 Qwen...（支援直接拖曳 .txt / .md / .pdf 檔案至此加入對話知識庫）"
        type="textarea"
        :rows="2"
        resize="none"
        :disabled="isLoading || !hasRoom"
        @keydown.enter.prevent="handleSend"
      />
      
      <div class="flex justify-between items-center mt-2 pt-1 border-t border-[#f9fafb]">
        <div class="flex items-center gap-1.5 select-none">
          <el-switch v-model="webSearch" :disabled="!hasRoom" active-text="搜尋網路" inline-prompt style="--el-switch-on-color: #64b5f6;" />
        </div>
        <div class="flex items-center">
          <span class="text-xs text-[#9ca3af] mr-4 hidden sm:inline">按 Enter 傳送訊息</span>
          <el-button type="primary" class="!rounded-lg !px-5 !bg-[#64b5f6] !border-[#64b5f6]" :loading="isLoading" :disabled="!hasRoom" @click="handleSend">傳送</el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, defineProps, defineEmits } from 'vue';
import { useChatStore } from '../stores/chat'; // 確保路徑與您的專案一致

const props = defineProps({ 
  isLoading: Boolean, 
  hasRoom: Boolean, 
  uploadedFiles: { type: Array, default: () => [] } 
});
const emit = defineEmits(['send']);

const chatStore = useChatStore(); 
const messageText = ref('');
const webSearch = ref(false);

const handleSend = () => {
  if (!messageText.value.trim() || props.isLoading) return;
  emit('send', { text: messageText.value.trim(), search: webSearch.value });
  messageText.value = '';
};

// 🎯 觸發 RAG 刪除控制（改用瀏覽器原生強固版 confirm）
const handleRemoveFile = async (fileName) => {
  if (!fileName) {
    console.error("[RAG-DELETE] 找不到檔案名稱，無法執行刪除");
    return;
  }

  console.log(`[RAG-DELETE] 使用者點擊了刪除按鈕，目標檔案: ${fileName}`);

  // 🚀 使用原生瀏覽器視窗，絕對不會因為 CSS 遮擋而隱形
  const isConfirmed = window.confirm(`確定要將「${fileName}」從目前聊天室的知識庫中移除嗎？這將會同步清除所有已建立的 Qwen 向量小抄。`);
  
  if (isConfirmed) {
    try {
      console.log(`[RAG-DELETE] 開始調用 Pinia 刪除 Action... 房間ID: ${chatStore.currentRoomId}`);
      
      // 核心呼叫
      await chatStore.deleteRoomFileAction(chatStore.currentRoomId, fileName);
      
      console.log(`[RAG-DELETE] Pinia Action 執行完畢`);
    } catch (err) {
      console.error("[RAG-DELETE] 調用 Pinia 發生未預期錯誤:", err);
    }
  } else {
    console.log("[RAG-DELETE] 使用者取消了刪除");
  }
};
</script>


