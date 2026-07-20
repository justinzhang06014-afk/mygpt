<!-- src/components/ChatRoom.vue -->
<!-- src/components/ChatRoom.vue -->
<template>
  <div 
    class="chat-layout-container relative flex w-full h-[calc(100vh-40px)] max-w-6xl mx-auto my-5 border border-[#e5e7eb] shadow-xl rounded-2xl overflow-hidden bg-white"
    @dragenter.prevent="handleDragEnter"
    @dragover.prevent
    @dragleave.prevent="handleDragLeave"
    @drop.prevent="handleFileDrop"
  >
    <!-- RAG 檔案拖曳遮罩 (🔒 Bug 1 防禦：只有在一般舊世界 RAG 模式下才允許觸發拖曳入庫) -->
    <div v-if="isDragging && !chatStore.currentAgentId" class="absolute inset-0 z-50 bg-[#e3f2fd]/90 backdrop-blur-xs flex flex-col items-center justify-center border-4 border-dashed border-[#64b5f6] rounded-2xl transition-all duration-200">
      <div class="text-6xl animate-bounce mb-4">📎</div>
      <h3 class="text-xl font-semibold text-[#0d47a1]">放開滑鼠即可入庫</h3>
      <p class="text-sm text-[#42a5f5] mt-1">將檔案無縫加入當前聊天室的 Qwen 專屬知識庫 (.txt / .md / .pdf)</p>
    </div>

    <!-- 左側積木：聊天室管理 (不需更改，內部 filteredRooms 會自動由 Pinia 大腦隔離過濾) -->
    <SidebarRooms 
      :store="chatStore" 
      @create="handleCreateNewChat"
      @select="handleSelectRoom" 
      @rename="handleRenameRoom" 
      @delete="handleDeleteRoom" 
    />

    <!-- 右側主區域 -->
    <div class="chat-main-wrapper flex-1 flex flex-col overflow-hidden bg-white">
      
      <!-- ========================================================================= -->
      <!-- ✨ 模式一：專家工作室大廳 (當 isAgentMarketMode 為 true 時強烈渲染) -->
      <!-- ========================================================================= -->
      <template v-if="chatStore.isAgentMarketMode">
        <!-- 大廳專屬高質感 Header -->
        <div class="chat-header py-4 px-6 bg-[#fcfdfe] border-b border-[#f3f4f6] flex items-center justify-between">
          <div class="flex items-center gap-3">
            <div class="w-3 h-3 rounded-full bg-[#67c23a]"></div>
            <h1 class="text-lg font-semibold text-[#1f2937] tracking-wide">✨ 專屬大腦助理工作坊</h1>
          </div>
          <el-button type="success" size="small" plain round @click="handleOpenCreateAgentDialog">
            ＋ 捏造全新大腦助理
          </el-button>
        </div>

        <!-- 專家卡片大廳流 -->
        <el-scrollbar class="flex-1 bg-[#fafbfc] p-6">
          <div class="max-w-4xl mx-auto">
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              
              <!-- 專家卡片積木 -->
              <div 
                v-for="agent in chatStore.agents" 
                :key="agent.id"
                @click="chatStore.enterAgentWorkspace(agent.agent_id)"
                class="bg-white border border-[#e5e7eb] hover:border-[#67c23a] p-5 rounded-2xl cursor-pointer shadow-3xs hover:shadow-md transition-all duration-200 flex flex-col gap-3 group relative overflow-hidden"
              >
                <!-- 卡片點綴裝飾 -->
                <div class="absolute top-0 right-0 w-16 h-16 bg-[#f0f9eb] rounded-bl-full flex items-center justify-center translate-x-4 -translate-y-4 group-hover:translate-x-2 group-hover:-translate-y-2 transition-transform">
                  <span class="text-xs mr-3 mt-3 opacity-60">💼</span>
                </div>

                <div class="flex items-center gap-3">
                  <div class="w-10 h-10 rounded-xl bg-[#f0f9eb] border border-[#b3e19d] flex items-center justify-center text-lg shrink-0">
                    🤖
                  </div>
                  <div class="min-w-0">
                    <h3 class="font-semibold text-[#1f2937] group-hover:text-[#67c23a] transition-colors truncate pr-4">
                      {{ agent.name }}
                    </h3>
                    <p class="text-[11px] text-[#9ca3af] mt-0.5">
                      隔離編碼: {{ agent.agent_id }}
                    </p>
                  </div>
                </div>

                <div class="text-xs text-[#6b7280] bg-[#f9fafb] p-3 rounded-xl line-clamp-2 min-h-[40px] border border-[#f3f4f6]">
                  {{ agent.system_prompt || '暫無自訂系統提示詞。' }}
                </div>
                <!-- 🎯 【全新新增】極簡高質感物理大掃除按鈕 -->
                <!-- 🔒 核心關鍵：使用 @click.stop 阻斷冒泡，拒絕點擊刪除時誤切進房間 -->
                <div class="flex justify-end items-center mt-1 border-t border-[#f9fafb] pt-2">
                  <el-button 
                    type="danger" 
                    size="small" 
                    link
                    icon="Delete"
                    @click.stop="handleDeleteAgent(agent.agent_id)"
                  >
                    銷毀大腦助理
                  </el-button>
                </div>

              </div>

            </div>

            <!-- 空狀態防護 -->
            <div v-if="!chatStore.agents || chatStore.agents.length === 0" class="flex flex-col items-center justify-center py-20 text-[#9ca3af] gap-2">
              <span class="text-4xl">🔮</span>
              <p class="text-sm">工作室內尚無自訂助理，點擊右上角立即打造專屬大腦！</p>
            </div>
          </div>
        </el-scrollbar>
      </template>

      <!-- ========================================================================= -->
      <!-- 💬 模式二：原有主聊天視窗 (當非大廳模式時調度渲染) -->
      <!-- ========================================================================= -->
      <template v-else>
        <!-- 頂部高質感 Header (🔒 Bug 1 優化：綠色與藍色雙世界極限對稱) -->
        <div class="chat-header py-4 px-6 bg-white border-b border-[#f3f4f6] flex items-center justify-between">
          <div class="flex items-center gap-3">
            <!-- 專家世界綠色指示燈 vs 舊世界藍色閃爍燈 -->
            <div 
              class="w-3 h-3 rounded-full" 
              :class="chatStore.currentAgentId ? 'bg-[#67c23a]' : 'bg-[#64b5f6] animate-pulse'"
            ></div>
            <h1 class="text-lg font-semibold text-[#1f2937] tracking-wide">{{ currentRoomTitle }}</h1>
          </div>
          
          <!-- 💡 智慧小標：若身處特定辦公室，提示共享記憶狀態 -->
          <span v-if="chatStore.currentAgentId" class="text-xs text-[#67c23a] bg-[#f0f9eb] px-3 py-1 rounded-full font-medium flex items-center gap-1.5">
            <span>🤖</span> <span>{{ chatStore.currentAgent?.name }} 辦公室 (跨對話共享記憶啟用)</span>
          </span>
          <span v-else class="text-xs text-[#9ca3af] bg-[#f3f4f6] px-3 py-1 rounded-full font-medium">
            即時搜尋 ＋ RAG 知識庫啟用版
          </span>
        </div>

        <!-- 中間對話展示流 -->
        <el-scrollbar class="chat-window flex-1 bg-[#f9f9f9]" ref="scrollbarRef">
          <div v-if="!chatStore.currentRoomId" class="h-full flex flex-col items-center justify-center text-[#9ca3af] gap-2 py-20">
            <span class="text-4xl">👋</span>
            <p class="text-sm">歡迎！請在左側選擇或建立一個聊天室開始對話。</p>
          </div>

          <div v-else class="chat-content-inner p-6 max-w-3xl mx-auto flex flex-col gap-6">
            <MessageBubble 
              v-for="msg in chatStore.messages" :key="msg.id" 
              :msg="msg" 
              :is-editing="editingId === msg.id"
              :is-loading="chatStore.isLoading"
              @start-edit="startEdit"
              @cancel-edit="cancelEdit"
              @submit-edit="submitEdit"
              @retract="handleRetract"
            />

            <!-- AI 思考中動畫 (🔒 Bug 1 修正：思考字樣依據身分動態對位，不穿幫) -->
            <div v-if="chatStore.isLoading" class="flex w-full gap-4 flex-row">
              <div class="w-9 h-9 rounded-xl flex items-center justify-center text-base bg-white border border-[#e5e7eb] shrink-0">🤖</div>
              <div class="bubble px-4 py-3 rounded-2xl rounded-tl-none border bg-white text-[15px] text-[#6b7280] flex items-center gap-2">
                <el-icon class="is-loading" :class="chatStore.currentAgentId ? 'text-[#67c23a]' : 'text-[#64b5f6]'"><Loading /></el-icon> 
                <span class="animate-pulse">
                  {{ chatStore.currentAgentId ? `${chatStore.currentAgent?.name} 正在深度檢索日記並推理...` : 'Qwen 正在翻閱知識庫並思考中...' }}
                </span>
              </div>
            </div>
          </div>
        </el-scrollbar>

        <!-- 下方輸入控制區 (🔒 Bug 1 終極絕殺：透過 uploaded-files 傳入。當前為 Agent 房時，傳空陣列，下方藍色 RAG 膠囊秒消失，留給 RAG 絕對乾淨的視窗！) -->
        <ChatInputArea 
          :is-loading="chatStore.isLoading" 
          :has-room="!!chatStore.currentRoomId" 
          :uploaded-files="chatStore.currentAgentId ? [] : chatStore.currentRoomFiles"
          @send="handleSend" 
        />
      </template>

    </div>
  </div>

  <!-- ========================================================================= -->
  <!-- 🛠️ 大廳專屬：【捏造全新大腦助理】Element Plus 彈窗組件 -->
  <!-- ========================================================================= -->
  <el-dialog 
    v-model="createAgentDialogVisible" 
    title="✨ 捏造全新 AI 大腦助理" 
    width="420px" 
    append-to-body
    class="rounded-2xl"
  >
    <el-form label-position="top">
      <el-form-item label="🧠 AI 助手大腦名稱" required>
        <el-input 
          v-model="newAgentName" 
          placeholder="例如：台股分析師、寵物行為專家..." 
          clearable 
          maxlength="15"
          show-word-limit
        />
      </el-form-item>
      <el-form-item label="📜 專家核心 Prompt 定制 (非必填)">
        <el-input 
          v-model="newAgentPrompt" 
          type="textarea" 
          :rows="4"
          placeholder="自訂此專家的性格與回覆偏好。留空則由後端自動賦予基本人格精緻提示詞。" 
          maxlength="200"
          show-word-limit
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <div class="flex justify-end gap-2">
        <el-button @click="createAgentDialogVisible = false">取消</el-button>
        <el-button type="success" :loading="isCreatingAgent" @click="submitCreateCustomAgent">確認建立專家大腦</el-button>
      </div>
    </template>
  </el-dialog>
</template>



<script setup>
import { ref, onMounted, nextTick, computed } from 'vue';
import { useChatStore } from '../stores/chat';
import { Loading } from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import axios from 'axios';

// 引入剛剛拆分出來的精緻小積木
import SidebarRooms from './SidebarRooms.vue';
import MessageBubble from './MessageBubble.vue';
import ChatInputArea from './ChatInputArea.vue';

const chatStore = useChatStore();
const scrollbarRef = ref(null);
const editingId = ref(null);
const isDragging = ref(false); // 控制拖曳天藍色遮罩的開關

// =========================================================================
// ✨ 多智慧體大廳（Agent Market）新增控制變數
// =========================================================================
const createAgentDialogVisible = ref(false);
const newAgentName = ref('');
const newAgentPrompt = ref('');
const isCreatingAgent = ref(false);

// 打開大廳的「捏造助理」彈窗
const handleOpenCreateAgentDialog = () => {
  newAgentName.value = '';
  newAgentPrompt.value = '';
  createAgentDialogVisible.value = true;
};

// 提交大腦捏造：打給後端已通電的 POST /api/agents 端點
const submitCreateCustomAgent = async () => {
  if (!newAgentName.value.trim()) {
    ElMessage.warning('請輸入助手專屬功能稱呼！');
    return;
  }

  try {
    isCreatingAgent.value = true;
    
    // 呼叫升級後的 Pinia Action 實寫入庫
    const newAgent = await chatStore.createCustomAgentAction(
      newAgentName.value,
      newAgentPrompt.value
    );

    ElMessage.success(`🎉 專家大腦 [${newAgent.name}] 捏造成功！已自動部署物理記憶鏈結。`);
    createAgentDialogVisible.value = false;
  } catch (err) {
    console.error('捏造專家大腦失敗:', err);
    ElMessage.error('伺服器大腦捏造失敗，請檢查資料庫通電日誌。');
  } finally {
    isCreatingAgent.value = false;
  }
};

// =========================================================================
// 💬 核心滾動與標題計算
// =========================================================================
const scrollToBottom = () => {
  nextTick(() => { 
    if (scrollbarRef.value) {
      setTimeout(() => scrollbarRef.value.setScrollTop(999999), 50); 
    }
  });
};

const currentRoomTitle = computed(() => {
  if (!chatStore.rooms || !chatStore.currentRoomId) return 'Qwen AI 智慧聯網助理';
  const activeRoom = chatStore.rooms.find(r => r.id === chatStore.currentRoomId);
  if (!activeRoom) return '新對話聊天室';

  // 💡 體驗細節進化：如果是在某個特定的 AI 專家辦公室名下，在房間標題前標註專家後綴
  if (chatStore.currentAgentId && chatStore.currentAgent) {
    return `[${chatStore.currentAgent.name}] ── ${activeRoom.title}`;
  }
  return activeRoom.title;
});

// =========================================================================
// 🌟 RAG 拖曳檔案核心事件處理 (100% 完整保留您原有的精髓)
// =========================================================================
const handleDragEnter = () => { if (chatStore.currentRoomId) isDragging.value = true; };
const handleDragLeave = (e) => { if (e.clientX === 0 && e.clientY === 0) isDragging.value = false; };

const handleFileDrop = async (e) => {
  isDragging.value = false;
  if (!chatStore.currentRoomId) return;

  const files = e.dataTransfer.files;
  if (files.length === 0) return;

  const targetFile = files[0];
  if (!targetFile.name.endsWith('.txt') && !targetFile.name.endsWith('.md') && !targetFile.name.endsWith('.pdf')) {
    ElMessage.error('目前的知識庫只支援上傳 .txt 或 .md 或 .pdf 的純文字檔案！');
    return;
  }

  const formData = new FormData();
  formData.append('file', targetFile);

  try {
    chatStore.isLoading = true;
    ElMessage.info(`正在上傳並將 ${targetFile.name} 進行向量化切片中...`);
    
    const res = await axios.post(`http://127.0.0.1:5165/api/rooms/${chatStore.currentRoomId}/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });

    ElMessage.success(`🎉 ${targetFile.name} 已成功加入本對話知識庫！共切分成 ${res.data.chunksCount} 個 RAG 小抄段落。`);
    await chatStore.fetchCurrentRoomFilesAction(chatStore.currentRoomId);
  } catch (err) {
    console.error('上傳文件 RAG 失敗:', err);
    ElMessage.error(err.response?.data || '上傳失敗，請檢查 C# 與 Python 服務是否暢通。');
  } finally {
    chatStore.isLoading = false;
  }
};

// =========================================================================
// 🛠️ 房間增刪查改控制方法
// =========================================================================
const handleCreateNewChat = async () => {
  await chatStore.createNewRoomAction();
  scrollToBottom();
};

const handleSelectRoom = async (id) => { 
  await chatStore.switchRoomAction(id); 
  scrollToBottom(); 
};

const handleRenameRoom = (room) => {
  ElMessageBox.prompt('請輸入新名稱：', '改名', { inputValue: room.title }).then(({ value }) => {
    chatStore.updateRoomTitleAction(room.id, value);
  });
};

const handleDeleteRoom = (id) => chatStore.deleteRoomAction(id);

const handleSend = ({ text, search }) => {
  chatStore.sendMessageAction({ roomId: chatStore.currentRoomId, content: text, isWebSearch: search });
  scrollToBottom();
};

const handleRetract = (id) => chatStore.deleteMessage(id);
const startEdit = (msg) => editingId.value = msg.id;
const cancelEdit = () => editingId.value = null;
const submitEdit = ({ id, text, search }) => {
  chatStore.updateMessage(id, text, search);
  editingId.value = null;
};

// =========================================================================
// 🔄 生命週期初始化掛載
// =========================================================================
onMounted(async () => {
  // 1. 讀取所有歷史房間
  await chatStore.fetchRoomsAction();
  
  // 2. 終極保險：如果重新整理網頁時已經有預設的 currentRoomId，強迫它在掛載時再重新整理一次檔案清單並置底
  if (chatStore.currentRoomId) {
    await chatStore.fetchCurrentRoomFilesAction(chatStore.currentRoomId);
    scrollToBottom();
  }
});
const isDeletingLock = ref(false);
// 🎯 在外層宣告一個防抖鎖，防止使用者在非同步期間重複點擊

const handleDeleteAgent = (incomingId) => {
    // 🔒 1. 資源鎖防護
    if (isDeletingLock.value) return;

    let realAgentId = incomingId;
    if (typeof incomingId === 'number' && chatStore.agents) {
        const found = chatStore.agents.find(a => a.id === incomingId);
        if (found) realAgentId = found.agent_id || found.agentId;
    }
    
    if (!realAgentId) return;

    // 🚀 2. 調用 Element 彈窗
    ElMessageBox.confirm(
        '此操作將連同該專家大腦、其底下所有房間對話，以及硬碟實體長期記憶檔案一併徹底永久銷毀，確定執行物理抄家？',
        '🚨 終極銷毀警告',
        {
            confirmButtonText: '確定要誅Agent九族嗎',
            cancelButtonText: '取消',
            type: 'warning',
            distinguishCancelAndClose: true, // 🔒 升級防禦：強迫區分關閉與取消，拒絕事件混淆
            customClass: 'rounded-2xl'
        }
    ).then(() => {
        // 🔒 3. 使用者點擊「確認」後，立刻切斷所有 UI 聯動，將任務丟給背景獨立函數執行
        executePhysicalDelete(realAgentId);
    }).catch((action) => {
        console.log("[前端調試] 彈窗安全關閉或使用者取消，行動代碼:", action);
    });
};

// 🖥️ 🎯 核心獨立執行函數：與 UI 彈窗完全解耦，專職衝向後端與 Hermes 線
const executePhysicalDelete = async (agentId) => {
    try {
        isDeletingLock.value = true;
        console.warn("[背景抄家線] 🚀 已經與彈窗完成政治隔離，獨立向 C# 警察發送抄家封包:", agentId);
        
        // 呼叫 chat.js 寫好的 action
        const success = await chatStore.deleteAgentAction(agentId);
        
        if (success) {
            ElMessage({ type: 'success', message: '該 AI 專家大腦及實體磁碟日記已安全回歸塵土！' });
        } else {
            ElMessage({ type: 'error', message: '資料庫或實體硬碟大掃除發生錯誤。' });
        }
    } catch (err) {
        console.error("[背景抄家線] ❌ 執行發生崩潰:", err);
    } finally {
        // 解鎖，恢復點擊功能
        isDeletingLock.value = false;
    }
};


</script>


<style scoped>
/* 1. 您原本舊有的高質感 RAG 文本與藍色膠囊防禦樣式 */
.white-space-pre-wrap { white-space: pre-wrap; }
.scrollbar-thin::-webkit-scrollbar { height: 4px; }
.scrollbar-thin::-webkit-scrollbar-thumb { background: #e5e7eb; border-radius: 10px; }

/* 🌟 2. 額外防禦補強：確保自訂專家 Prompt 的「兩行省略號」在所有主流瀏覽器完美卡位 */
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 🌟 3. 體驗加分：為大廳的專家卡片提供一個超流暢的微軟/Dify 風格懸停陰影 */
.shadow-3xs {
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.03), 0 1px 6px -1px rgba(0, 0, 0, 0.02);
}
</style>

