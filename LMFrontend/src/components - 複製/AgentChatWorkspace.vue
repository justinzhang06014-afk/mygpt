<template>
  <!-- 雙欄主要容器：科技業高質感自適應版面，融入清爽淡藍色基底 -->
  <div 
    class="flex-1 flex overflow-hidden w-full relative select-none bg-[#f4f8fc]"
    @dragenter.prevent="handleDragEnter"
    @dragover.prevent
    @dragleave.prevent="handleDragLeave"
    @drop.prevent="handleFileDrop"
    @mousemove="handleMouseMove"
    @mouseup="handleMouseUp"
    @mouseleave="handleMouseUp"
  >
    
    <!-- RAG 檔案拖曳天藍色科技感遮罩 -->
    <div v-if="isDragging && !props.chatStore.currentAgentId" class="absolute inset-0 z-50 bg-[#e0f2fe]/95 backdrop-blur-md flex flex-col items-center justify-center border-4 border-dashed border-[#3b82f6] rounded-2xl transition-all duration-200 shadow-2xl">
      <div class="text-7xl animate-bounce mb-4">📎</div>
      <h3 class="text-2xl font-bold text-[#1d4ed8]">放開滑鼠即可入庫</h3>
      <p class="text-sm text-[#3b82f6] mt-2 font-medium">將檔案無縫加入當前聊天室的 Qwen 專屬知識庫 (.txt / .md / .pdf)</p>
    </div>

    <!-- ========================================================================= -->
    <!-- 【左欄】主要對話視窗 (融入極光淡藍色與 SaaS 呼吸感) -->
    <!-- ========================================================================= -->
    <div class="flex-1 flex flex-col h-full bg-[#f4f8fc] overflow-hidden">
      
      <!-- 頂部對話標題與智慧小標 (毛玻璃半透明質感) -->
      <div class="chat-header py-4 px-6 bg-white/90 backdrop-blur-md border-b border-[#e2e8f0] flex items-center justify-between shrink-0 shadow-2xs relative z-10">
        <div class="flex items-center gap-3">
          <div class="w-3 h-3 rounded-full" :class="props.chatStore.currentAgentId ? 'bg-[#67c23a] shadow-[0_0_8px_#67c23a]' : 'bg-[#3b82f6] animate-pulse shadow-[0_0_8px_#3b82f6]'"></div>
          <h1 class="text-base font-bold text-[#0f172a] tracking-wide">{{ currentRoomTitle }}</h1>
        </div>
        
        <span v-if="props.chatStore.currentAgentId" class="text-xs text-[#16a34a] bg-[#f0fdf4] border border-[#bbf7d0] px-3 py-1 rounded-full font-semibold flex items-center gap-1.5 shadow-2xs">
          <span>🤖</span> <span>{{ props.chatStore.currentAgent?.name }} 辦公室 (跨對話共享記憶啟用)</span>
        </span>
        <span v-else class="text-xs text-[#2563eb] bg-[#eff6ff] border border-[#bfdbfe] px-3 py-1 rounded-full font-semibold shadow-2xs">
          即時搜尋 ＋ RAG 知識庫啟用版
        </span>
      </div>

      <!-- 對話內容展示滾動區 (調整寬度黃金分割比) -->
      <el-scrollbar class="chat-window flex-1" ref="scrollbarRef">
        <div v-if="!props.chatStore.currentRoomId" class="h-full flex flex-col items-center justify-center text-[#94a3b8] gap-3 py-32">
          <span class="text-5xl animate-pulse">👋</span>
          <p class="text-sm font-medium">歡迎使用！請在左側選擇或建立一個聊天室開始深度對話。</p>
        </div>

        <!-- 🚀 視覺微調：改為 max-w-4xl，符合人眼閱讀習慣 -->
        <div v-else class="chat-content-inner p-6 max-w-4xl mx-auto flex flex-col gap-6 w-full">
          
          <!-- ⚡ 終端機日誌面板 -->
          <div v-if="props.chatStore.isLoading" class="cli-logs-container bg-[#0b0f17] rounded-xl p-4 border border-[#67c23a]/40 shadow-[0_0_15px_rgba(103,194,58,0.1)] font-mono text-xs text-[#67c23a] flex flex-col gap-2 transition-all">
            <div class="flex items-center justify-between border-b border-[#1e293b] pb-2 mb-1">
              <span class="text-[#64748b] text-[10px] tracking-widest font-sans font-black">HERMES CLI EXECUTION LOGS</span>
              <span class="flex h-2 w-2 relative">
                <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#67c23a] opacity-75"></span>
                <span class="relative inline-flex rounded-full h-2 w-2 bg-[#67c23a]"></span>
              </span>
            </div>
            <div class="text-[#a6e22e] flex items-center gap-2">⚡ <span class="text-[#e2e8f0]">Executing:</span> hermes chat --agent {{ props.chatStore.currentAgentId || 'default' }}</div>
            <div class="text-[#66d9ef] animate-pulse">⚙️ [Preparing tool: web_fetch] ...</div>
            <div class="text-[#f92672] opacity-90">⚠️ [System Warning] Bypassing deprecated memory pointers...</div>
            <div class="text-[#94a3b8] text-[11px] opacity-80">> Streaming CLI token chunks safely to chat.js...</div>
          </div>

          <!-- 原有的訊息聊天泡泡組件 -->
          <MessageBubble 
            v-for="msg in props.chatStore.messages" :key="msg.id" 
            :msg="msg" 
            :is-editing="editingId === msg.id"
            :is-loading="props.chatStore.isLoading"
            @start-edit="startEdit"
            @cancel-edit="cancelEdit"
            @submit-edit="submitEdit"
            @retract="handleRetract"
          />

          <!-- AI 思考中動畫 -->
          <div v-if="props.chatStore.isLoading" class="flex w-full gap-4 flex-row">
            <div class="w-9 h-9 rounded-xl flex items-center justify-center text-base bg-white border border-[#e2e8f0] shadow-2xs shrink-0">🤖</div>
            <div class="bubble px-4 py-3 rounded-2xl rounded-tl-none border border-[#e2e8f0] bg-white text-[14px] text-[#475569] flex items-center gap-2.5 shadow-2xs">
              <el-icon class="is-loading text-[#3b82f6]" :class="{ 'text-[#67c23a]': props.chatStore.currentAgentId }"><Loading /></el-icon> 
              <span class="animate-pulse font-medium">
                {{ props.chatStore.currentAgentId ? `${props.chatStore.currentAgent?.name} 正在深度檢索日記並推理...` : 'Qwen 正在翻閱知識庫並思考中...' }}
              </span>
            </div>
          </div>
        </div>
      </el-scrollbar>

      <!-- 下方訊息輸入控制區 -->
      <div class="w-full max-w-4xl mx-auto px-6 pb-5 bg-transparent shrink-0">
        <ChatInputArea 
          :is-loading="props.chatStore.isLoading" 
          :has-room="!!props.chatStore.currentRoomId" 
          :uploaded-files="props.chatStore.currentAgentId ? [] : props.chatStore.currentRoomFiles"
          @send="handleSend" 
        />
      </div>
    </div>

    <!-- ↕️ 智慧科技感拖曳控制線 -->
    <div 
      class="w-1 h-full hover:w-1.5 bg-[#e2e8f0] hover:bg-[#3b82f6] cursor-col-resize transition-all duration-150 relative z-30 shrink-0 select-none shadow-xs"
      @mousedown="handleMouseDown"
    ></div>
    <!-- ========================================================================= -->
    <!-- 【右欄】智能體核心主控台 (解鎖固定寬度，升級微藍科技玻璃質感) -->
    <!-- ========================================================================= -->
    <div 
      class="h-full bg-[#f8fafc]/95 border-l border-[#e2e8f0] flex flex-col overflow-hidden select-none backdrop-blur-md"
      :style="{ width: sidebarWidth + 'px' }"
    >
      <!-- 側邊欄上方標頭 -->
      <div class="p-4 border-b border-[#e2e8f0] bg-white flex items-center gap-2 shrink-0 shadow-3xs">
        <span class="text-base filter drop-shadow-sm">⚙️</span>
        <span class="font-bold text-sm text-[#0f172a] tracking-wide">智能體核心主控台</span>
      </div>

      <!-- 控制面板內部滾動項目 -->
      <el-scrollbar class="flex-1 p-4 bg-gradient-to-b from-[#f8fafc] to-[#f1f5f9]">
        <div class="flex flex-col gap-5 pb-6">
          
          <!-- a. 模型隨機選單區塊 -->
          <div class="bg-white p-3.5 rounded-2xl border border-[#e2e8f0] shadow-3xs hover:border-[#bfdbfe] transition-all duration-200 flex flex-col gap-2.5">
            <label class="text-xs font-bold text-[#475569] flex items-center justify-between">
              <span class="flex items-center gap-1">🔽 選擇 LLM 模型</span>
              <span v-if="selectedModel === 'random'" class="text-[10px] font-semibold text-blue-600 bg-blue-50 border border-blue-100 px-2 py-0.5 rounded-md animate-pulse">🎲 隨機精選中</span>
            </label>
            
            <el-select v-model="selectedModel" placeholder="請選取運算模型" class="w-full tech-select" size="small">
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
              class="justify-start mt-0.5 text-[11px] font-semibold text-[#2563eb] hover:text-[#1d4ed8]"
              @click="openAddModelDialog"
            >
              新增自訂底層模型
            </el-button>
          </div>

          <!-- b. 技能商店與外掛開關 -->
          <div class="bg-white p-3.5 rounded-2xl border border-[#e2e8f0] shadow-3xs hover:border-[#bfdbfe] transition-all duration-200 flex flex-col gap-2.5">
            <div class="flex items-center justify-between">
              <label class="text-xs font-bold text-[#475569]">🛠️ 技能商店與外掛</label>
              <span class="text-[10px] font-semibold text-[#16a34a] bg-[#f0fdf4] border border-[#bbf7d0] px-1.5 py-0.5 rounded-md">可動態連動</span>
            </div>
            <div class="flex flex-col gap-2 mt-0.5">
              <div class="flex items-center justify-between p-2 bg-[#f8fafc] rounded-xl border border-[#e2e8f0] hover:bg-[#f0f7ff] transition-colors">
                <span class="text-xs font-medium text-[#334155]">🌐 聯網搜尋 (web_fetch)</span>
                <el-checkbox v-model="toolsConfig.webSearch" size="small" />
              </div>
              <div class="flex items-center justify-between p-2 bg-[#f8fafc] rounded-xl border border-[#e2e8f0] hover:bg-[#f0f7ff] transition-colors">
                <span class="text-xs font-medium text-[#334155]">🧮 計算機 (calculator)</span>
                <el-checkbox v-model="toolsConfig.calculator" size="small" />
              </div>
            </div>
            <div class="text-[10px] text-[#64748b] mt-0.5 italic border-t border-dashed border-[#e2e8f0] pt-2 leading-relaxed">
              💡 提示：後續可在此點選並將不同獨立 Agent 加入本技能商店。
            </div>
          </div>

          <!-- c. 記憶庫管理分頁 -->
          <div class="bg-white p-3.5 rounded-2xl border border-[#e2e8f0] shadow-3xs hover:border-[#bfdbfe] transition-all duration-200 flex flex-col gap-2.5">
            <label class="text-xs font-bold text-[#475569]">🧠 記憶庫管理控制台</label>
            <div class="text-xs text-[#475569] bg-[#f8fafc] p-3 rounded-xl border border-[#e2e8f0] leading-relaxed font-medium">
              當前 Agent 的長短期記憶庫（`MEMORY.md`）目前由外部核心代理同步監控。
            </div>
            <el-button 
              type="primary" 
              size="small" 
              plain 
              class="w-full mt-0.5 font-bold !bg-[#eff6ff] !text-[#2563eb] !border-[#bfdbfe] hover:!bg-[#dbeafe] rounded-xl" 
              icon="Monitor"
              @click="handleOpenMemoryDashboard"
            >
              開啟外部記憶庫控制台 ↗
            </el-button>
          </div>

          <!-- d. 安全與行為規範設定（已補回開頭 div 標籤） -->
          <div class="bg-white p-3.5 rounded-2xl border border-[#e2e8f0] shadow-3xs relative min-h-[115px] overflow-hidden group">
            <label class="text-xs font-bold text-[#475569]">🛡️ 安全與行為規範設定</label>
            <div class="absolute inset-0 bg-white/90 backdrop-blur-xs flex flex-col items-center justify-center p-3 text-center transition-all duration-300 group-hover:bg-[#f8fafc]/90">
              <span class="text-base animate-pulse">🔒</span>
              <span class="text-[11px] font-black text-[#ef4444] mt-1.5 tracking-wider">資安行為防禦規範</span>
              <span class="text-[10px] text-[#64748b] mt-0.5 transform scale-95">功能尚未開通，等待階段三解鎖</span>
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
    class="rounded-2xl tech-dialog shadow-2xl border border-[#dbeafe]"
  >
    <div class="text-xs text-[#b45309] bg-[#fffbeb] p-3.5 rounded-xl mb-4 leading-relaxed border border-[#fef3c7] font-medium shadow-3xs">
      ⚠️ 這裡填寫的欄位名稱將完美映射至 Hermes Agent 底層的配置 structures，請確保模型參數對齊。
    </div>
    
    <el-form label-position="top" class="tech-form">
      <el-form-item required label="模型辨識名稱 (default)" class="!mb-3">
        <el-input v-model="newModelForm.default" placeholder="例如: Qwen/Qwen3.6-27B" />
      </el-form-item>
      <el-form-item required label="金鑰憑證 (api_key)" class="!mb-3">
        <el-input v-model="newModelForm.api_key" placeholder="輸入 AINX-F78D... 密鑰憑證" show-password />
      </el-form-item>
      <el-form-item required label="基礎端點接口 (base_url)" class="!mb-3">
        <el-input v-model="newModelForm.base_url" placeholder="https://phison.com" />
      </el-form-item>
      <el-form-item required label="供應商類型 (provider)" class="!mb-1">
        <el-input v-model="newModelForm.provider" placeholder="例如: custom" />
      </el-form-item>
    </el-form>

    <template #footer>
      <div class="flex justify-end gap-2 pt-2 border-t border-[#f1f5f9]">
        <el-button size="small" class="rounded-lg" @click="addModelDialogVisible = false">取消</el-button>
        <el-button size="small" type="primary" class="rounded-lg font-bold" @click="submitAddNewModel">儲存模型設定</el-button>
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
// ↕️ 智慧型左右動態拉伸側邊欄控制（科技業極客調校版）
// =========================================================================
const sidebarWidth = ref(320); // 預設加寬至 320px
const isResizing = ref(false);

const handleMouseDown = (e) => {
  isResizing.value = true;
  document.body.style.userSelect = 'none';
};

const handleMouseMove = (e) => {
  if (!isResizing.value) return;
  
  // 計算出滑鼠相對於視窗右側的距離
  const containerWidth = window.innerWidth;
  const newWidth = containerWidth - e.clientX;
  
  // 設置合理的科技業寬度限制，確保任何寬度下資訊都不擠壓
  if (newWidth >= 300 && newWidth <= 500) {
    sidebarWidth.value = newWidth;
  }
};

const handleMouseUp = () => {
  if (isResizing.value) {
    isResizing.value = false;
    document.body.style.userSelect = '';
  }
};

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
  
  // 💡 當前身處特定 Agent 辦公室名下時，在房間標題前標註專家後綴
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

  const targetFile = files[0]; // 修正精準鎖定單一檔案
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
/* 精細科技微弱陰影控制 */
.shadow-3xs {
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03), 0 4px 12px -2px rgba(15, 23, 42, 0.02);
}
.shadow-2xs {
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
}

/* ⚡ CLI 終端機日誌面板高質感進場動畫與呼吸微光 */
.cli-logs-container {
  animation: fadeInTerminal 0.5s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes fadeInTerminal {
  from { 
    opacity: 0; 
    transform: translateY(10px); 
    filter: blur(4px);
  }
  to { 
    opacity: 1; 
    transform: translateY(0);
    filter: blur(0);
  }
}

/* ↕️ 智慧型拖曳軸：滑鼠滑過時呈現高科技亮藍脈衝線 */
.cursor-col-resize {
  transition: background-color 0.2s, box-shadow 0.2s;
}
.cursor-col-resize:hover {
  box-shadow: 0 0 10px rgba(59, 130, 246, 0.6);
}

/* ========================================================================= */
/* 🎛️ Element Plus 深度科技化樣式優化 */
/* ========================================================================= */
:deep(.tech-select .el-input__wrapper) {
  background-color: #f8fafc !important;
  border-radius: 10px !important;
  box-shadow: 0 0 0 1px #e2e8f0 inset !important;
  padding: 4px 10px !important;
  transition: all 0.2s ease;
}

:deep(.tech-select .el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px #bfdbfe inset !important;
  background-color: #f0f7ff !important;
}

:deep(.tech-select .el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px #3b82f6 inset, 0 0 0 4px rgba(59, 130, 246, 0.1) !important;
  background-color: #ffffff !important;
}

/* 彈窗高階整容 (圓角化與淡藍邊框) */
:deep(.tech-dialog) {
  background: rgba(255, 255, 255, 0.95) !important;
  backdrop-filter: blur(16px) !important;
  border: 1px solid #dbeafe !important;
}

:deep(.tech-dialog .el-dialog__header) {
  padding-bottom: 12px !important;
  border-bottom: 1px solid #f1f5f9 !important;
  margin-right: 0 !important;
}

:deep(.tech-dialog .el-dialog__title) {
  font-size: 15px !important;
  font-weight: 700 !important;
  color: #0f172a !important;
}

:deep(.tech-form .el-form-item__label) {
  font-size: 11px !important;
  font-weight: 700 !important;
  color: #475569 !important;
  margin-bottom: 4px !important;
}

:deep(.tech-form .el-input__wrapper) {
  border-radius: 10px !important;
  box-shadow: 0 0 0 1px #e2e8f0 inset !important;
}
</style>
