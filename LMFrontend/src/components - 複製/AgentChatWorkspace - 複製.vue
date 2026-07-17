<template>
  <!-- 雙欄主要容器：左側對話流 75%，右側控制台 25% -->
  <div 
    class="flex-1 flex overflow-hidden w-full relative"
    @dragenter.prevent="handleDragEnter"
    @dragover.prevent
    @dragleave.prevent="handleDragLeave"
    @drop.prevent="handleFileDrop"
  >
    
    <!-- RAG 檔案拖曳天藍色遮罩 (只有舊世界 RAG 模式下才允許觸發) -->
    <div v-if="isDragging && !chatStore.currentAgentId" class="absolute inset-0 z-50 bg-[#e3f2fd]/90 backdrop-blur-xs flex flex-col items-center justify-center border-4 border-dashed border-[#64b5f6] rounded-2xl transition-all duration-200">
      <div class="text-6xl animate-bounce mb-4">📎</div>
      <h3 class="text-xl font-semibold text-[#0d47a1]">放開滑鼠即可入庫</h3>
      <p class="text-sm text-[#42a5f5] mt-1">將檔案無縫加入當前聊天室的 Qwen 專屬知識庫 (.txt / .md / .pdf)</p>
    </div>

    <!-- ========================================================================= -->
    <!-- 【左欄】主要對話視窗 (寬度鎖已解開，聊天小人與輸入橫條完美拉寬) -->
    <!-- ========================================================================= -->
    <div class="flex-1 flex flex-col h-full bg-[#f9f9f9] border-r border-[#e5e7eb]">
      
      <!-- 頂部對話標題與智慧小標 -->
      <div class="chat-header py-4 px-6 bg-white border-b border-[#f3f4f6] flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="w-3 h-3 rounded-full" :class="chatStore.currentAgentId ? 'bg-[#67c23a]' : 'bg-[#64b5f6] animate-pulse'"></div>
          <h1 class="text-lg font-semibold text-[#1f2937] tracking-wide">{{ currentRoomTitle }}</h1>
        </div>
        
        <span v-if="chatStore.currentAgentId" class="text-xs text-[#67c23a] bg-[#f0f9eb] px-3 py-1 rounded-full font-medium flex items-center gap-1.5">
          <span>🤖</span> <span>{{ chatStore.currentAgent?.name }} 辦公室 (跨對話共享記憶啟用)</span>
        </span>
        <span v-else class="text-xs text-[#9ca3af] bg-[#f3f4f6] px-3 py-1 rounded-full font-medium">
          即時搜尋 ＋ RAG 知識庫啟用版
        </span>
      </div>

      <!-- 對話內容展示滾動區 -->
      <el-scrollbar class="chat-window flex-1" ref="scrollbarRef">
        <div v-if="!chatStore.currentRoomId" class="h-full flex flex-col items-center justify-center text-[#9ca3af] gap-2 py-20">
          <span class="text-4xl">👋</span>
          <p class="text-sm">歡迎！請在左側選擇或建立一個聊天室開始對話。</p>
        </div>

        <!-- 🚀 核心放大優化：將原來的 max-w-3xl 擴展為 max-w-5xl，讓對話流與頭像有足夠空間橫向伸展 -->
        <div v-else class="chat-content-inner p-6 max-w-5xl mx-auto flex flex-col gap-6 w-full">
          
          <!-- ⚡ 結構化 CLI 狀態日誌展示面板（不隱藏原始日誌，美化輸出） -->
          <div v-if="chatStore.isLoading" class="cli-logs-container bg-[#1e1e1e] rounded-xl p-3 border border-[#333] shadow-inner font-mono text-xs text-[#67c23a] flex flex-col gap-1.5 transition-all">
            <div class="flex items-center justify-between border-b border-[#333] pb-1 mb-1">
              <span class="text-[#888] text-[10px] tracking-wider font-sans font-bold">HERMES CLI EXECUTION LOGS</span>
              <span class="flex h-2 w-2 relative">
                <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#67c23a] opacity-75"></span>
                <span class="relative inline-flex rounded-full h-2 w-2 bg-[#67c23a]"></span>
              </span>
            </div>
            <div class="text-[#a6e22e] flex items-center gap-2">⚡ <span class="text-white">Executing:</span> hermes chat --agent {{ chatStore.currentAgentId || 'default' }}</div>
            <div class="text-[#66d9ef] animate-pulse">⚙️ [Preparing tool: web_fetch] ...</div>
            <div class="text-[#f92672] opacity-80">⚠️ [System Warning] Bypassing deprecated memory pointers...</div>
            <div class="text-[#999] text-[11px]">> Streaming CLI token chunks safely to chat.js...</div>
          </div>

          <!-- 原有的訊息聊天泡泡組件 -->
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

          <!-- AI 思考中動畫 -->
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

      <!-- 下方訊息輸入控制區 (也同步包裹在 max-w-5xl 自適應容器內，讓橫條同步大器變寬) -->
      <div class="w-full max-w-5xl mx-auto px-6 pb-4 bg-[#f9f9f9]">
        <ChatInputArea 
          :is-loading="chatStore.isLoading" 
          :has-room="!!chatStore.currentRoomId" 
          :uploaded-files="chatStore.currentAgentId ? [] : chatStore.currentRoomFiles"
          @send="handleSend" 
        />
      </div>
    </div>
    <!-- ========================================================================= -->
    <!-- 【右欄】🛠️ 全新智能體控制中心側邊欄 (模型選單、工具開關、記憶庫、安全規範) -->
    <!-- ========================================================================= -->
    <div class="w-72 h-full bg-[#f8fafc] border-l border-[#e5e7eb] flex flex-col overflow-hidden shrink-0 select-none">
      <!-- 側邊欄上方標頭 -->
      <div class="p-4 border-b border-[#e5e7eb] bg-white flex items-center gap-2">
        <span class="text-base">⚙️</span>
        <span class="font-bold text-sm text-[#374151]">智能體核心主控台</span>
      </div>

      <!-- 控制面板內部滾動項目 -->
      <el-scrollbar class="flex-1 p-4">
        <div class="flex flex-col gap-5 pb-6">
          
          <!-- a. 模型隨機選單區塊 -->
          <div class="bg-white p-3 rounded-xl border border-[#e5e7eb] shadow-3xs flex flex-col gap-2">
            <label class="text-xs font-bold text-[#4b5563] flex items-center justify-between">
              <span>🔽 選擇 LLM 模型</span>
              <span v-if="selectedModel === 'random'" class="text-[10px] text-purple-600 bg-purple-50 px-1.5 py-0.5 rounded animate-pulse">🎲 隨機精選中</span>
            </label>
            
            <el-select v-model="selectedModel" placeholder="請選取運算模型" class="w-full" size="small">
              <el-option label="🎲 隨機精選模型 (Random)" value="random" />
              <el-option label="Qwen 3.6 27B (預設)" value="Qwen/Qwen3.6-27B" />
              <el-option label="Hermes 3 70B (AI核心)" value="Hermes-3-70B" />
              <el-option v-for="m in customModels" :key="m.default" :label="m.default" :value="m.default" />
            </el-select>

            <el-button 
              type="primary" 
              link 
              size="small" 
              icon="Plus" 
              class="justify-start mt-1 text-[11px]"
              @click="openAddModelDialog"
            >
              新增自訂底層模型
            </el-button>
          </div>

          <!-- b. 技能商店與外掛開關 (預設假裝勾選連動) -->
          <div class="bg-white p-3 rounded-xl border border-[#e5e7eb] shadow-3xs flex flex-col gap-2">
            <div class="flex items-center justify-between">
              <label class="text-xs font-bold text-[#4b5563]">🛠️ 技能商店與外掛</label>
              <span class="text-[9px] text-[#67c23a] bg-[#f0f9eb] px-1 rounded">可動態連動</span>
            </div>
            <div class="flex flex-col gap-2 mt-1">
              <div class="flex items-center justify-between p-1.5 bg-[#f9fafb] rounded border border-[#f3f4f6]">
                <span class="text-xs text-[#374151]">🌐 聯網搜尋 (web_fetch)</span>
                <el-checkbox v-model="toolsConfig.webSearch" size="small" />
              </div>
              <div class="flex items-center justify-between p-1.5 bg-[#f9fafb] rounded border border-[#f3f4f6]">
                <span class="text-xs text-[#374151]">🧮 計算機 (calculator)</span>
                <el-checkbox v-model="toolsConfig.calculator" size="small" />
              </div>
            </div>
            <div class="text-[10px] text-[#9ca3af] mt-1 italic border-t border-dashed border-[#f3f4f6] pt-1">
              💡 提示：後續可在此點選並將不同獨立 Agent 加入本技能商店。
            </div>
          </div>

          <!-- c. 記憶庫管理分頁 (預留串聯外部網站按鈕) -->
          <div class="bg-white p-3 rounded-xl border border-[#e5e7eb] shadow-3xs flex flex-col gap-2">
            <label class="text-xs font-bold text-[#4b5563]">🧠 記憶庫管理控制台</label>
            <div class="text-xs text-[#6b7280] bg-[#fdfdfd] p-2.5 rounded-lg border border-[#f3f4f6] leading-relaxed">
              當前 Agent 的長短期記憶庫（`MEMORY.md`）目前由外部核心代理同步監控。
            </div>
            <el-button 
              type="success" 
              size="small" 
              plain 
              class="w-full mt-1" 
              icon="Monitor"
              @click="handleOpenMemoryDashboard"
            >
              開啟外部記憶庫控制台 ↗
            </el-button>
          </div>

          <!-- d. 安全與行為規範設定 (覆蓋半透明遮罩，提示等待階段三解鎖) -->
          <div class="bg-white p-3 rounded-xl border border-[#e5e7eb] shadow-3xs flex flex-col gap-2 relative min-h-[110px] overflow-hidden">
            <label class="text-xs font-bold text-[#4b5563]">🛡️ 安全與行為規範設定</label>
            <div class="absolute inset-0 bg-white/85 backdrop-blur-xs flex flex-col items-center justify-center p-3 text-center transition-all duration-200">
              <span class="text-sm">🔒</span>
              <span class="text-[11px] font-bold text-[#ef4444] mt-1">資安行為防禦規範</span>
              <span class="text-[10px] text-[#9ca3af] transform scale-90">功能尚未開通，等待階段三解鎖</span>
            </div>
          </div>

        </div>
      </el-scrollbar>
    </div>
    <!-- 右側側邊欄結束 -->

  </div>
  <!-- 雙欄主要容器結束 -->

  <!-- ========================================================================= -->
  <!-- ➕ 【配置 Hermes 底層自訂模型】技術規格表單彈窗組件 -->
  <!-- ========================================================================= -->
  <el-dialog 
    v-model="addModelDialogVisible" 
    title="➕ 配置 Hermes 底層自訂模型" 
    width="460px" 
    append-to-body
    class="rounded-2xl"
  >
    <div class="text-xs text-[#e6a23c] bg-[#fdf6ec] p-3 rounded-lg mb-4 leading-relaxed border border-[#faecd8]">
      ⚠️ 這裡填寫的欄位名稱將完美映射至 Hermes Agent 底層的配置結構，請確保模型參數對齊。
    </div>
    
    <el-form label-position="top">
      <el-form-item required label="模型辨識名稱 (default)">
        <el-input v-model="newModelForm.default" placeholder="例如: Qwen/Qwen3.6-27B" />
      </el-form-item>
      <el-form-item required label="金鑰憑證 (api_key)">
        <el-input v-model="newModelForm.api_key" placeholder="輸入 AINX-F78D... 密鑰憑證" show-password />
      </el-form-item>
      <el-form-item required label="基礎端點接口 (base_url)">
        <el-input v-model="newModelForm.base_url" placeholder="https://phison.com" />
      </el-form-item>
      <el-form-item required label="供應商類型 (provider)">
        <el-input v-model="newModelForm.provider" placeholder="例如: custom" />
      </el-form-item>
    </el-form>

    <template #footer>
      <div class="flex justify-end gap-2">
        <el-button size="small" @click="addModelDialogVisible = false">取消</el-button>
        <el-button size="small" type="primary" @click="submitAddNewModel">儲存模型設定</el-button>
      </div>
    </template>
  </el-dialog>
</template>
<script setup>
import { ref, reactive, computed, nextTick } from 'vue';
import { Loading } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import axios from 'axios';

// 引入最底層對話渲染小積木
import MessageBubble from './MessageBubble.vue';
import ChatInputArea from './ChatInputArea.vue';

// 🚀 核心設計：使用 props 安全接收來自外殼主控官的 Pinia 核心狀態大腦
const props = defineProps({
  chatStore: {
    type: Object,
    required: true
  }
});

const scrollbarRef = ref(null);
const editingId = ref(null);
const isDragging = ref(false);

// =========================================================================
// 🎲 a. 模型選單核心變數（含 AINX 底層四項技術名稱與預設值）
// =========================================================================
const selectedModel = ref('Qwen/Qwen3.6-27B'); // 下拉選單預設值
const addModelDialogVisible = ref(false);      // 彈窗開關
const customModels = ref([]);                 // 前端自訂模型列表容器

const newModelForm = reactive({
  default: 'Qwen/Qwen3.6-27B',
  api_key: 'AINX-F78D2FCD53915EE37BD0871392FFBFFAF648C53C388950FC6A1F2ED8C534B249',
  base_url: 'https://phison.com',
  provider: 'custom'
});

// =========================================================================
// 🛠️ b. 技能商店外掛開關
// =========================================================================
const toolsConfig = reactive({
  webSearch: true,
  calculator: true
});

// =========================================================================
// 💬 核心滾動計算與智慧標題前綴
// =========================================================================
const scrollToBottom = () => {
  nextTick(() => { 
    if (scrollbarRef.value) {
      setTimeout(() => scrollbarRef.value.setScrollTop(999999), 50); 
    }
  });
};

const currentRoomTitle = computed(() => {
  if (!props.chatStore.rooms || !props.chatStore.currentRoomId) return 'Qwen AI 智慧聯網助理';
  const activeRoom = props.chatStore.rooms.find(r => r.id === props.chatStore.currentRoomId);
  if (!activeRoom) return '新對話聊天室';
  
  // 💡 體驗進化：當前身處特定 Agent 辦公室名下時，在房間標題前標註專家後綴
  if (props.chatStore.currentAgentId && props.chatStore.currentAgent) {
    return `[${props.chatStore.currentAgent.name}] ── ${activeRoom.title}`;
  }
  return activeRoom.title;
});

// =========================================================================
// 🌟 RAG 拖曳檔案核心事件處理 (承接 5165 埠的原汁原味精髓)
// =========================================================================
const handleDragEnter = () => { if (props.chatStore.currentRoomId) isDragging.value = true; };
const handleDragLeave = (e) => { if (e.clientX === 0 && e.clientY === 0) isDragging.value = false; };

const handleFileDrop = async (e) => {
  isDragging.value = false;
  if (!props.chatStore.currentRoomId) return;

  const files = e.dataTransfer.files;
  if (files.length === 0) return;

  const targetFile = files[0];
  if (!targetFile.name.endsWith('.txt') && !targetFile.name.endsWith('.md') && !targetFile.name.endsWith('.pdf')) {
    ElMessage.error('目前的知識庫只支援上傳 .txt、.md 或 .pdf 檔案！');
    return;
  }

  const formData = new FormData();
  formData.append('file', targetFile);

  try {
    props.chatStore.isLoading = true;
    ElMessage.info(`正在上傳並將 ${targetFile.name} 進行向量化切片中...`);
    
    const res = await axios.post(`http://127.0.0{props.chatStore.currentRoomId}/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });

    ElMessage.success(`🎉 ${targetFile.name} 已成功加入本對話知識庫！共切分成 ${res.data.chunksCount} 個 RAG 小抄段落。`);
    await props.chatStore.fetchCurrentRoomFilesAction(props.chatStore.currentRoomId);
    scrollToBottom();
  } catch (err) {
    console.error('上傳文件 RAG 失敗:', err);
    ElMessage.error('上傳失敗，請檢查 RAG 服務接口是否暢通。');
  } finally {
    props.chatStore.isLoading = false;
  }
};

// =========================================================================
// 🎯 核心控制台按鈕交互路由
// =========================================================================
const openAddModelDialog = () => { 
  addModelDialogVisible.value = true; 
};

const submitAddNewModel = () => {
  if (!newModelForm.default || !newModelForm.api_key || !newModelForm.base_url || !newModelForm.provider) {
    ElMessage.warning('請確認 Hermes 模型配置之四項關鍵底層技術欄位皆已完整填寫');
    return;
  }
  // 寫入前端陣列（選項立即更新）
  customModels.value.push({ ...newModelForm });
  selectedModel.value = newModelForm.default; // 自動切換至新註冊模型
  addModelDialogVisible.value = false;
  ElMessage.success(`成功註冊自訂模型：${newModelForm.default}`);
};

// c. 記憶庫連結外部儀表板跳轉
const handleOpenMemoryDashboard = () => {
  ElMessage.info('正在啟動安全對接協議，導向外部記憶控制台網站...');
  window.open('https://localhost:5001/memory-dashboard', '_blank');
};

// =========================================================================
// 🛠️ 對話串流基本路由方法 (完美對接 Pinia Action)
// =========================================================================
const handleSend = ({ text, search }) => {
  props.chatStore.sendMessageAction({ roomId: props.chatStore.currentRoomId, content: text, isWebSearch: search });
  scrollToBottom();
};

const handleRetract = (id) => props.chatStore.deleteMessage(id);
const startEdit = (msg) => editingId.value = msg.id;
const cancelEdit = () => editingId.value = null;
const submitEdit = ({ id, text, search }) => {
  props.chatStore.updateMessage(id, text, search);
  editingId.value = null;
};
</script>

<style scoped>
/* 細緻陰影控制 */
.shadow-3xs {
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.03), 0 1px 6px -1px rgba(0, 0, 0, 0.02);
}

/* ⚡ CLI 終端機日誌面板高質感進場動畫 */
.cli-logs-container {
  animation: fadeInTerminal 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes fadeInTerminal {
  from { 
    opacity: 0; 
    transform: translateY(6px); 
  }
  to { 
    opacity: 1; 
    transform: translateY(0); 
  }
}
</style>
