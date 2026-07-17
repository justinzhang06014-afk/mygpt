<!-- src/components/ChatRoom.vue -->
<template>
  <div 
    class="chat-layout-container relative flex w-full h-[calc(100vh-24px)] max-w-[98vw] mx-auto my-3 border border-[#dbeefc] shadow-2xl rounded-2xl overflow-hidden tech-bg"
    @dragenter.prevent="handleDragEnter"
    @dragover.prevent
    @dragleave.prevent="handleDragLeave"
    @drop.prevent="handleFileDrop"
  >
    <!-- RAG 檔案拖曳遮罩 (🔒 Bug 1 防禦：只有在一般舊世界 RAG 模式下才允許觸發拖曳入庫) -->
    <div v-if="isDragging && !chatStore.currentAgentId" class="absolute inset-0 z-50 bg-[#e3f2fd]/90 backdrop-blur-xs flex flex-col items-center justify-center border-4 border-dashed border-[#64b5f6] rounded-2xl transition-all duration-200">
      <div class="text-7xl animate-bounce mb-4">📎</div>
      <h3 class="text-2xl font-bold text-[#0d47a1]">放開滑鼠即可入庫</h3>
      <p class="text-base text-[#42a5f5] mt-2">將檔案無縫加入當前聊天室的 Qwen 專屬知識庫 (.txt / .md / .pdf)</p>
    </div>

    <!-- 1. 左側積木：聊天室管理 (寬度適中) -->
    <SidebarRooms 
      class="w-72 shrink-0 border-r border-[#e5e7eb]"
      :store="chatStore" 
      @create="handleCreateNewChat"
      @select="handleSelectRoom" 
      @rename="handleRenameRoom" 
      @delete="handleDeleteRoom" 
    />

        <!-- 2. 中間主區域：專家工作室大廳 vs 核心對話視窗 (視覺比例全面舒展放大) -->
    <div class="chat-main-wrapper flex-1 flex flex-col overflow-hidden bg-white shadow-sm">
      
      <!-- ========================================================================= -->
      <!-- ✨ 模式一：專家工作室大廳 (當 isAgentMarketMode 為 true 時強烈渲染) -->
      <!-- ========================================================================= -->
      <template v-if="chatStore.isAgentMarketMode">
        <!-- 大廳專屬高質感 Header -->
        <div class="chat-header py-5 px-8 bg-[#fcfdfe] border-b border-[#f3f4f6] flex items-center justify-between">
          <div class="flex items-center gap-3">
            <div class="w-3.5 h-3.5 rounded-full bg-[#0ea5e9]"></div>
            <h1 class="text-xl font-bold text-[#1f2937] tracking-wide">✨ 專屬大腦助理工作坊</h1>
          </div>
          <el-button type="primary" size="default" plain round @click="handleOpenCreateAgentDialog">
            ＋ 捏造全新大腦助理
          </el-button>
        </div>

        <!-- 專家卡片大廳流 (排版放大，最大寬度提升至 max-w-5xl) -->
        <el-scrollbar class="flex-1 bg-[#fafbfc] p-8">
          <div class="max-w-5xl mx-auto">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
              
              <!-- 專家卡片積木 -->
              <div 
                v-for="agent in chatStore.agents" 
                :key="agent.id"
                @click="chatStore.enterAgentWorkspace(agent.agent_id)"
                class="bg-white border border-[#e5e7eb] hover:border-[#0ea5e9] p-6 rounded-2xl cursor-pointer shadow-3xs hover:shadow-lg transition-all duration-200 flex flex-col gap-4 group relative overflow-hidden"
              >
                <!-- 卡片點綴裝飾 -->
                <div class="absolute top-0 right-0 w-20 h-20 bg-[#e0f2fe] rounded-bl-full flex items-center justify-center translate-x-4 -translate-y-4 group-hover:translate-x-2 group-hover:-translate-y-2 transition-transform">
                  <span class="text-base mr-3 mt-3 opacity-60">💼</span>
                </div>

                <div class="flex items-center gap-4">
                  <div class="w-12 h-12 rounded-xl bg-[#e0f2fe] border border-[#7dd3fc] flex items-center justify-center text-2xl shrink-0">
                    🤖
                  </div>
                  <div class="min-w-0">
                    <h3 class="text-lg font-bold text-[#1f2937] group-hover:text-[#0ea5e9] transition-colors truncate pr-4">
                      {{ agent.name }}
                    </h3>
                    <p class="text-xs text-[#9ca3af] mt-0.5">
                      隔離編碼: {{ agent.agent_id }}
                    </p>
                  </div>
                </div>

                <div class="text-sm text-[#6b7280] bg-[#f9fafb] p-4 rounded-xl line-clamp-2 min-h-[48px] border border-[#f3f4f6] leading-relaxed">
                  {{ agent.system_prompt || '暫無自訂系統提示詞。' }}
                </div>

                <!-- 🔌 目前常駐的 MCP 徽章：讀不到或還沒設定過就不顯示這段 -->
                <div v-if="agentResidentMcpNames[agent.agent_id]?.length" class="flex flex-wrap gap-1.5">
                  <span
                    v-for="mcpName in agentResidentMcpNames[agent.agent_id]"
                    :key="mcpName"
                    class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#dbeafe] text-[#1d4ed8]"
                  >
                    🔌 {{ mcpName }}
                  </span>
                </div>

                <!-- 🔒 核心關鍵：使用 @click.stop 阻斷冒泡，拒絕點擊刪除時誤切進房間 -->
                <div class="flex justify-end items-center gap-2 mt-2 border-t border-[#f9fafb] pt-3">
                  <el-button
                    type="primary"
                    size="small"
                    link
                    icon="Share"
                    @click.stop="handleOpenCloneModal(agent.agent_id)"
                  >
                    複製
                  </el-button>
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
            <div v-if="!chatStore.agents || chatStore.agents.length === 0" class="flex flex-col items-center justify-center py-32 text-[#9ca3af] gap-3">
              <span class="text-5xl">🔮</span>
              <p class="text-base font-medium">工作室內尚無自訂助理，點擊右上角立即打造專屬大腦！</p>
            </div>
          </div>
        </el-scrollbar>
      </template>

      <!-- ========================================================================= -->
      <!-- 💬 模式二：原有主聊天視窗 (當非大廳模式時調度渲染) -->
      <!-- ========================================================================= -->
      <template v-else>
        <!-- 頂部高質感 Header (🔒 綠色與藍色雙世界極限對稱) -->
        <div class="chat-header py-5 px-8 bg-white border-b border-[#f3f4f6] flex items-center justify-between shadow-xs">
          <div class="flex items-center gap-3">
            <div 
              class="w-3.5 h-3.5 rounded-full" 
              :class="chatStore.currentAgentId ? 'bg-[#0ea5e9]' : 'bg-[#64b5f6] animate-pulse'"
            ></div>
            <h1 class="text-xl font-bold text-[#1f2937] tracking-wide">{{ currentRoomTitle }}</h1>
          </div>
          
          <!-- 💡 智慧小標：提示共享記憶狀態 -->
          <span v-if="chatStore.currentAgentId" class="text-sm text-[#0ea5e9] bg-[#e0f2fe] px-4 py-1.5 rounded-full font-semibold flex items-center gap-2 shadow-3xs">
            <span>🤖</span> <span>{{ chatStore.currentAgent?.name }} 辦公室 (跨對話共享記憶啟用)</span>
          </span>
          <span v-else class="text-xs text-[#9ca3af] bg-[#f3f4f6] px-4 py-1.5 rounded-full font-medium">
            即時搜尋 ＋ RAG 知識庫啟用版
          </span>
        </div>

        <!-- 💡 聊天門檻提示：對話累積夠豐富時，提醒使用者可以匯出成技能包 -->
        <div
          v-if="chatStore.currentAgentId && chatStore.messages.length > 40 && !exportBannerDismissed"
          class="mx-8 mt-4 px-4 py-2.5 bg-[#f0f7ff] border border-[#d6e4ff] rounded-xl flex items-center justify-between gap-3"
        >
          <span class="text-xs text-[#1d39c4]">💡 這個對話已經很豐富了，要不要把 {{ chatStore.currentAgent?.name }} 匯出成技能包？</span>
          <div class="flex items-center gap-2 shrink-0">
            <el-button size="small" type="primary" plain round :loading="isExportingFromBanner" @click="handleExportFromBanner">📤 匯出成技能包</el-button>
            <el-button size="small" link @click="exportBannerDismissed = true">不用了</el-button>
          </div>
        </div>

        <!-- 中間對話展示流 (🔒 任務三防禦：審查中自動套用半透明磨砂，阻斷滑鼠點擊) -->
        <el-scrollbar
          class="chat-window flex-1 bg-[#f8fafc] transition-all duration-300"
          :class="{ 'opacity-40 pointer-events-none filter blur-[0.5px]': isApprovalFrozen }" 
          ref="scrollbarRef"
        >
          <div v-if="!chatStore.currentRoomId" class="h-full flex flex-col items-center justify-center text-[#9ca3af] gap-3 py-32">
            <span class="text-5xl">👋</span>
            <p class="text-base font-medium">歡迎！請在左側選擇或建立一個聊天室開始對話。</p>
          </div>

          <div v-else class="chat-content-inner p-8 max-w-4xl mx-auto flex flex-col gap-8 text-[16px]">
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

            <!-- AI 思考中動畫 (思考字樣依據身分動態對位，不穿幫) -->
            <div v-if="chatStore.isLoading" class="flex w-full gap-4 flex-row animate-fade-in">
              <div class="w-10 h-10 rounded-xl flex items-center justify-center text-xl bg-white border border-[#e5e7eb] shrink-0 shadow-3xs">🤖</div>
              <div class="bubble px-5 py-3.5 rounded-2xl rounded-tl-none border bg-white text-[15px] text-[#4b5563] flex items-center gap-3 shadow-3xs">
                <el-icon class="is-loading text-lg" :class="chatStore.currentAgentId ? 'text-[#0ea5e9]' : 'text-[#64b5f6]'"><Loading /></el-icon> 
                <span class="font-medium tracking-wide">
                  {{ chatStore.currentAgentId ? `${chatStore.currentAgent?.name} 正在深度檢索日記並推理...` : 'Qwen 正在翻閱知識庫並思考中...' }}
                </span>
              </div>
            </div>
          </div>
        </el-scrollbar>

        <!-- 下方輸入控制區 (🔒 Bug 1 終極絕殺：當前為 Agent 房時，傳空陣列，下方藍色 RAG 膠囊秒消失) -->
        <ChatInputArea 
          :is-loading="chatStore.isLoading" 
          :has-room="!!chatStore.currentRoomId" 
          :uploaded-files="chatStore.currentAgentId ? [] : chatStore.currentRoomFiles"
          @send="handleSend" 
        />
      </template>

    </div>
        <!-- ========================================================================= -->
    <!-- 🧠 右側全新升級掛載：AI 專家大腦多功能動態側欄調度大廳 (Part C) -->
    <!-- ⚡ 完美包容大腦長期記憶 (Memory) 與您未來要開發的所有外掛技能 (Skills)！ -->
    <!-- ========================================================================= -->
    <RightDynamicSidebar
      v-if="!chatStore.isAgentMarketMode && chatStore.currentAgentId"
    />

  </div> <!-- 結束最外層巨幕化框架 chat-layout-container -->


  <!-- ========================================================================= -->
  <!-- 🧬 【真．複製新 Agent】彈窗組件 -->
  <!-- ========================================================================= -->
  <ForkAgentModal v-model="forkModalVisible" :preset-source-agent-id="forkPresetSourceId" />


  <!-- ========================================================================= -->
  <!-- ⚠️ 任務三全新掛載：【人機協同安全審查】凍結核心警告彈窗 -->
  <!-- ========================================================================= -->
  <el-dialog
    v-model="isApprovalFrozen"
    title="🚨 企業級人機協同安全審查"
    width="460px"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    :show-close="false"
    append-to-body
    class="approval-dialog rounded-2xl"
  >
    <div class="flex flex-col items-center gap-4 text-center py-2">
      <div class="w-16 h-16 rounded-full bg-[#fef3c7] flex items-center justify-center text-3xl animate-pulse text-[#d97706]">
        ⚠️
      </div>
      <div>
        <h3 class="text-lg font-bold text-[#1f2937]">Agent 請求執行需要人工核准的動作</h3>
        <p class="text-sm text-[#6b7280] mt-2 leading-relaxed">
          hermes 偵測到這個動作需要核准（可能是危險指令、記憶寫入、或技能安裝），這是 hermes 自己回報的真實內容：
        </p>
        <p v-if="approvalDetail.title" class="text-xs text-left text-[#92400e] bg-[#fffbeb] border border-[#fde68a] rounded-lg p-3 mt-3 font-mono whitespace-pre-wrap break-words">
          {{ approvalDetail.title }}
        </p>
        <pre v-if="approvalDetail.command" class="text-xs text-left text-[#92400e] bg-[#fffbeb] border border-[#fde68a] rounded-lg p-3 mt-2 font-mono whitespace-pre-wrap break-words m-0">{{ approvalDetail.command }}</pre>
      </div>
    </div>
    <template #footer>
      <!-- 🆕 0716：hermes acp 的 request_permission 會給幾種選項就顯示幾個按鈕（實測常見
           allow_once/allow_session/allow_always/reject_once/reject_always 五選一），
           不再寫死只有同意/拒絕兩顆按鈕 -->
      <div class="flex flex-col gap-2 w-full border-t border-[#f3f4f6] pt-4">
        <el-button
          v-for="opt in approvalDetail.options"
          :key="opt.option_id"
          :type="opt.kind && opt.kind.startsWith('allow') ? 'success' : 'danger'"
          plain
          class="w-full !rounded-xl py-3 font-semibold"
          :loading="isSubmittingApproval"
          @click="handleApprovalChoice(opt.option_id)"
        >
          {{ opt.kind && opt.kind.startsWith('allow') ? '🟢' : '🔴' }} {{ opt.name }}
        </el-button>
        <!-- 保底：萬一沒解析出任何選項（例如舊格式的純文字訊息），還是要讓使用者能拒絕掉，不會卡死 -->
        <el-button
          v-if="approvalDetail.options.length === 0"
          type="danger"
          class="w-full !rounded-xl py-3 font-semibold"
          :loading="isSubmittingApproval"
          @click="handleApprovalChoice('reject_once')"
        >
          🔴 拒絕
        </el-button>
      </div>
    </template>
  </el-dialog>


  <!-- ========================================================================= -->
  <!-- 🛠️ 大廳原有：【捏造全新大腦助理】Element Plus 彈窗組件 -->
  <!-- ========================================================================= -->
  <el-dialog
    v-model="createAgentDialogVisible"
    title="✨ 捏造全新 AI 大腦助理"
    width="560px"
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

      <!-- 🔌 MCP 工具勾選：清單即時從後台商店母版拉取，母版新增什麼這裡就自動多出什麼，不寫死 -->
      <el-form-item label="🔌 要不要先掛上幾個 MCP 工具（非必填）">
        <div v-if="createAgentMcpLoading" class="text-xs text-[#9ca3af] py-2">讀取 MCP 商店中...</div>
        <div v-else-if="createAgentMcpCatalog.length === 0" class="text-xs text-[#9ca3af] py-2">目前商店母版是空的，之後隨時可以在 Agent 建立後再去 MCP 商店加。</div>
        <div v-else class="flex flex-col gap-1.5 max-h-48 overflow-y-auto pr-1">
          <div
            v-for="mcp in createAgentMcpCatalog"
            :key="mcp.name"
            class="flex items-center justify-between gap-2 border border-[#f3f4f6] rounded-lg px-3 py-2"
          >
            <div class="min-w-0">
              <p class="text-sm font-medium truncate">{{ mcp.displayName || mcp.name }}</p>
              <p class="text-xs text-[#9ca3af] truncate">{{ mcp.description }}</p>
            </div>
            <el-select
              v-model="newAgentMcpSelections[mcp.name]"
              placeholder="不使用"
              size="small"
              style="width: 110px"
              clearable
            >
              <el-option label="📌 常駐" value="resident" />
              <el-option label="➕ 選配" value="optional_installed" />
            </el-select>
          </div>
        </div>
      </el-form-item>

      <!-- 🎯 基礎技能勾選：清單即時從後台精選目錄拉取，母版新增什麼這裡就自動多出什麼，不寫死。
           技能有沒有生效 hermes 純掃資料夾判斷，勾選後直接走 hermes skills install 裝進這個 agent -->
      <el-form-item label="🎯 要不要先裝幾個基礎技能（非必填）">
        <div v-if="createAgentSkillLoading" class="text-xs text-[#9ca3af] py-2">讀取精選技能清單中...</div>
        <div v-else-if="createAgentSkillCatalog.length === 0" class="text-xs text-[#9ca3af] py-2">目前精選清單是空的，之後隨時可以在 Agent 建立後去技能市集搜尋安裝（hermes 官方市集有 8 萬多個）。</div>
        <div v-else class="flex flex-col gap-1.5 max-h-40 overflow-y-auto pr-1">
          <label
            v-for="skill in createAgentSkillCatalog"
            :key="skill.key"
            class="flex items-start gap-2 border border-[#f3f4f6] rounded-lg px-3 py-2 cursor-pointer"
          >
            <input type="checkbox" v-model="newAgentSkillSelections[skill.key]" class="mt-1" />
            <div class="min-w-0">
              <p class="text-sm font-medium truncate">{{ skill.displayName || skill.key }}</p>
              <p class="text-xs text-[#9ca3af] truncate">{{ skill.description }}</p>
            </div>
          </label>
        </div>
      </el-form-item>

      <!-- 🛡️ Approval 開關：對照 hermes 自己原生的 3 個真實 schema 欄位，不是我們發明的 -->
      <el-form-item label="🛡️ 核准尺度（非必填，預設跟現有行為一致）">
        <div class="flex flex-col gap-2 w-full">
          <div class="flex items-center justify-between">
            <span class="text-sm">危險指令/寫檔核准模式</span>
            <el-select v-model="newAgentApprovals.mode" size="small" style="width: 160px">
              <el-option label="manual（全部都問）" value="manual" />
              <el-option label="smart（AI 自動判斷）" value="smart" />
              <el-option label="off（不問，風險自負）" value="off" />
            </el-select>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-sm">寫入記憶前先問我</span>
            <el-switch v-model="newAgentApprovals.memoryWriteApproval" />
          </div>
          <div class="flex items-center justify-between">
            <span class="text-sm">安裝/修改技能前先問我</span>
            <el-switch v-model="newAgentApprovals.skillsWriteApproval" />
          </div>
        </div>
      </el-form-item>
    </el-form>
    <template #footer>
      <div class="flex justify-end gap-2 border-t border-[#f3f4f6] pt-3">
        <el-button @click="createAgentDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="isCreatingAgent" @click="submitCreateCustomAgent">確認建立專家大腦</el-button>
      </div>
    </template>
  </el-dialog>
</template>



<script setup>
import { ref, onMounted, onUnmounted, nextTick, computed, watch } from 'vue';
import { useChatStore } from '../stores/chat';
import { Loading } from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import axios from 'axios';

// 引入剛剛拆分出來的精緻小積木
import SidebarRooms from './SidebarRooms.vue';
import MessageBubble from './MessageBubble.vue';
import ChatInputArea from './ChatInputArea.vue';


// import AgentMemoryPanel from './AgentMemoryPanel.vue'; // 🧠 Part 2 新增的核心記憶面板
import ForkAgentModal from './ForkAgentModal.vue';     // 🧬 Part 3 新增的細胞分裂彈窗
import RightDynamicSidebar from './RightDynamicSidebar.vue';// 🟢 替換並引入全新的一體化多功能動態側欄大廳：

const chatStore = useChatStore();
const scrollbarRef = ref(null);
const editingId = ref(null);
const isDragging = ref(false); // 控制拖曳天藍色遮罩的開關

// =========================================================================
// ✨ 多智慧體大廳（Agent Market）新增控制變數
// =========================================================================
const createAgentDialogVisible = ref(false);

// 🔌 每個 agent 目前的常駐 MCP 顯示名稱清單，key 是 agent_id，僅供大廳卡片顯示徽章用
const agentResidentMcpNames = ref({});
const newAgentName = ref('');
const newAgentPrompt = ref('');
const isCreatingAgent = ref(false);

// 🔌 建立彈窗專用：MCP 商店清單即時從母版拉，不寫死；newAgentMcpSelections 是 { mcpName: 'resident'|'optional_installed' }
const createAgentMcpCatalog = ref([]);
const createAgentMcpLoading = ref(false);
const newAgentMcpSelections = ref({});
// 🎯 建立彈窗專用：精選技能清單即時從後台拉，不寫死；newAgentSkillSelections 是 { skillKey: true/false }
const createAgentSkillCatalog = ref([]);
const createAgentSkillLoading = ref(false);
const newAgentSkillSelections = ref({});
// 🛡️ 建立彈窗專用：預設值刻意跟 services.py 目前的既有行為一致（manual/false/false），不選就等於維持原樣
const newAgentApprovals = ref({ mode: 'manual', memoryWriteApproval: false, skillsWriteApproval: false });

// 打開大廳的「捏造助理」彈窗
const handleOpenCreateAgentDialog = async () => {
  newAgentName.value = '';
  newAgentPrompt.value = '';
  newAgentMcpSelections.value = {};
  newAgentSkillSelections.value = {};
  newAgentApprovals.value = { mode: 'manual', memoryWriteApproval: false, skillsWriteApproval: false };
  createAgentDialogVisible.value = true;

  createAgentMcpLoading.value = true;
  try {
    const catalog = await chatStore.fetchMcpCatalogAction();
    // 母版是 { name: entry } 物件，這裡轉成陣列給 v-for 用；商店新增什麼，這裡下次打開就自動多出什麼
    createAgentMcpCatalog.value = Object.entries(catalog || {}).map(([name, entry]) => ({ name, ...entry }));
  } catch (err) {
    console.error('讀取 MCP 商店母版失敗:', err);
    createAgentMcpCatalog.value = [];
  } finally {
    createAgentMcpLoading.value = false;
  }

  createAgentSkillLoading.value = true;
  try {
    const skillCatalog = await chatStore.fetchSkillsCatalogAction();
    createAgentSkillCatalog.value = Object.entries(skillCatalog || {}).map(([key, entry]) => ({ key, ...entry }));
  } catch (err) {
    console.error('讀取精選技能清單失敗:', err);
    createAgentSkillCatalog.value = [];
  } finally {
    createAgentSkillLoading.value = false;
  }
};

// 提交大腦捏造：打給後端已通電的 POST /api/agents 端點，成功後再依序套用 MCP 選擇跟 approval 設定
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
    const newAgentId = newAgent.agent_id || newAgent.agentId;

    // 🔌 套用這次勾選的 MCP（agent 這時候已經存在，mcp.json 會即時建立在它自己的目錄下）
    const selectedMcpEntries = Object.entries(newAgentMcpSelections.value).filter(([, selection]) => !!selection);
    for (const [mcpName, selection] of selectedMcpEntries) {
      try {
        await chatStore.setAgentMcpSelectionAction(newAgentId, mcpName, selection);
      } catch (mcpErr) {
        console.error(`套用 MCP [${mcpName}] 選擇失敗:`, mcpErr);
        ElMessage.warning(`⚠️ 「${mcpName}」設定失敗，之後可以在 MCP 商店裡補設定`);
      }
    }

    // 🛡️ 套用 approval 設定（沒改過就是預設值，等於跟改動前行為一致，不影響既有邏輯）
    try {
      await chatStore.setAgentApprovalsAction(newAgentId, newAgentApprovals.value);
    } catch (approvalErr) {
      console.error('套用 approval 設定失敗:', approvalErr);
      ElMessage.warning('⚠️ 核准尺度設定失敗，之後可以再調整');
    }

    // 🎯 套用這次勾選的基礎技能：直接走 hermes skills install，跟技能市集搜尋安裝同一條路徑
    const selectedSkillEntries = createAgentSkillCatalog.value.filter(skill => newAgentSkillSelections.value[skill.key]);
    for (const skill of selectedSkillEntries) {
      try {
        await chatStore.installSkillFromHubAction(newAgentId, skill.identifier);
      } catch (skillErr) {
        console.error(`安裝技能 [${skill.key}] 失敗:`, skillErr);
        ElMessage.warning(`⚠️ 「${skill.displayName || skill.key}」安裝失敗，之後可以在技能市集裡補裝`);
      }
    }

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
    
    const res = await axios.post(`/api/rooms/${chatStore.currentRoomId}/upload`, formData, {
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

// 💡 多租戶隔離升級版
const handleSend = ({ text, search }) => {
  chatStore.sendMessageAction({ 
    roomId: chatStore.currentRoomId, 
    content: text, 
    isWebSearch: search,
    userId: chatStore.currentUserId // 👈 讓 sendMessageAction 可以一路打包丟給 C# 的 LlmController!
  });
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



// =========================================================================
// ⚠️ 任務三：人機協同審查凍結與細胞分裂狀態鎖
// =========================================================================
// =========================================================================
// ⚠️ 任務三：人機協同審查凍結與細胞分裂狀態鎖
// =========================================================================
const isApprovalFrozen = ref(false);       // 控制審查彈窗顯示，並將主對話視窗套用半透明磨砂凍結
const isSubmittingApproval = ref(false);   // 審查按鈕的非同步防重複點擊鎖

// 🆕 0716：main.py 現在送的是 JSON（{options:[{option_id,name,kind}], title, raw_input}），
// 不再是純文字。這裡統一解析成畫面要用的結構，解析失敗就退化成「只給拒絕」，不會卡死使用者。
const approvalRawPayload = ref('');
const approvalDetail = computed(() => {
  if (!approvalRawPayload.value) return { title: '', command: '', options: [] };
  try {
    const parsed = JSON.parse(approvalRawPayload.value);
    return {
      title: parsed.title || '',
      command: parsed.raw_input?.command || '',
      options: Array.isArray(parsed.options) ? parsed.options : [],
    };
  } catch {
    // 舊格式相容：萬一收到的還是純文字，直接當標題顯示
    return { title: approvalRawPayload.value, command: '', options: [] };
  }
});
const forkModalVisible = ref(false);       // 控制真．複製彈窗開關
const forkPresetSourceId = ref('');        // 大廳卡片點擊「複製」時，預先帶入的來源 Agent

// 🧬 從大廳卡片開啟複製彈窗，並預先帶入該卡片作為複製範本
const handleOpenCloneModal = (sourceAgentId) => {
  forkPresetSourceId.value = sourceAgentId;
  forkModalVisible.value = true;
};

// 💡 聊天門檻 banner：對話夠豐富時提示匯出成技能包
const exportBannerDismissed = ref(false);
const isExportingFromBanner = ref(false);
const handleExportFromBanner = async () => {
  if (!chatStore.currentAgentId) return;
  try {
    isExportingFromBanner.value = true;
    await chatStore.exportAgentAction(chatStore.currentAgentId, 'skill');
    ElMessage.success('📤 技能包已開始下載！');
    exportBannerDismissed.value = true;
  } catch (err) {
    console.error('匯出技能包失敗:', err);
    ElMessage.error(`匯出失敗：${err?.response?.data?.error || err?.message || '未知錯誤'}`);
  } finally {
    isExportingFromBanner.value = false;
  }
};

// 🆕 0716：不再是同意/拒絕二選一，改成把使用者點的按鈕對應的 option_id 直接送給
// hermes acp 的 request_permission（可能是 allow_once/allow_session/allow_always/
// reject_once/reject_always 任何一種，由 hermes 自己決定要提供哪些選項）
const handleApprovalChoice = async (optionId) => {
  if (!chatStore.currentRoomId || !optionId) return;
  try {
    isSubmittingApproval.value = true;
    await chatStore.submitApproveDecision(chatStore.currentRoomId, optionId);
    const isAllow = optionId.startsWith('allow');
    ElMessage({
      type: isAllow ? 'success' : 'warning',
      message: isAllow ? '🟢 已核准，Hermes 會繼續執行。' : '🔴 已拒絕，Hermes 不會執行這個動作。',
    });
    isApprovalFrozen.value = false;
    if (typeof window.__releaseApprovalLock === 'function') {
      window.__releaseApprovalLock();
    }
  } catch (err) {
    console.error('送出審查決定失敗:', err);
    ElMessage.error('通訊失敗，請檢查後端 Hermes 狀態機日誌。');
  } finally {
    isSubmittingApproval.value = false;
  }
};

// 💡 終極聯動保險：當組件掛載時，把觸發彈窗的開關註冊給 window，讓 Pinia Store 可以跨檔案喚醒它
window.__triggerApprovalModal = (payload) => {
  approvalRawPayload.value = payload || '';
  isApprovalFrozen.value = true;
};
onUnmounted(() => {
  if (window.__triggerApprovalModal) delete window.__triggerApprovalModal;
});

// 💡 請在 ChatRoom.vue 的最下方，將原本的 window.__triggerApprovalModal、
// window.addEventListener('hermes-approval-required'...) 以及 onMounted 通通刪除
// 100% 替換成下面這段標準、安全的生命週期程式碼：

// 💡 請確保你有從 'vue' 引入 watch
// import { ref, onMounted, watch } from 'vue';

// 封裝一個獨立的「通電啟動函式」
const initializeChatData = async () => {
  console.log(`[數據通電] 偵測到用戶 [${chatStore.currentUserId}]，開始注入多維狀態...`);
  
  // 🌐 4. 向後端拉取該使用者專屬的歷史聊天室列表 (Rooms)
  await chatStore.fetchRoomsAction();
  
  // 🧠 5. 動態拉起目前系統中捏造過的所有 Agent 總名冊
  if (typeof chatStore.fetchAgentsAction === 'function') {
      await chatStore.fetchAgentsAction();
  } else if (typeof chatStore.fetchAvailableForkAgents === 'function') {
      await chatStore.fetchAvailableForkAgents();
  }

  // 🔌 5b. 大廳卡片要顯示每個 agent 目前的常駐 MCP 徽章，平行讀取，讀不到就跳過不擋畫面
  loadAgentResidentMcpBadges();

  // 🔮 6. 歷史房號記憶恢復與右側面板同步
  if (chatStore.currentRoomId) {
    await chatStore.switchRoomAction(chatStore.currentRoomId);
    
    if (chatStore.currentAgentId && typeof chatStore.fetchAgentMemories === 'function') {
       await chatStore.fetchAgentMemories(chatStore.currentAgentId, 'memory');
       await chatStore.fetchAgentMemories(chatStore.currentAgentId, 'user');
    }
    scrollToBottom();
  }
};

// 🔌 大廳卡片用：平行讀取每個 agent 目前設為常駐的 MCP 顯示名稱，單一 agent 失敗不影響其他張卡片
const loadAgentResidentMcpBadges = () => {
  if (typeof chatStore.fetchAgentMcpStateAction !== 'function') return;
  for (const agent of chatStore.agents || []) {
    const agentId = agent.agent_id;
    if (!agentId) continue;
    chatStore.fetchAgentMcpStateAction(agentId)
      .then(servers => {
        const names = Object.values(servers || {})
          .filter(entry => entry.selection === 'resident')
          .map(entry => entry.displayName);
        agentResidentMcpNames.value = { ...agentResidentMcpNames.value, [agentId]: names };
      })
      .catch(() => {}); // 讀不到就靜默跳過，不影響大廳卡片正常顯示
  }
};

onMounted(async () => {
  console.log("🚀 [熱啟動] 頁面已順利掛載，啟動前端多維狀態自癒體系...");

  // 🛡️ 1. 安全隔離防線（跟模組層級那份重複註冊一次，確保重新掛載後還在）
  window.__triggerApprovalModal = (payload) => {
    approvalRawPayload.value = payload || '';
    isApprovalFrozen.value = true;
  };

  // 🛡️ 2. 掛載自訂事件監聽
  if (typeof handleGlobalApprovalSignal === 'function') {
    window.addEventListener('hermes-approval-required', handleGlobalApprovalSignal);
  }

  // 🛡️ 3. 多租戶身份自癒檢查 (異步防禦升級版)
  if (chatStore.currentUserId) {
    // 如果此時已經有身分了（例如 F5 續命過來的），直接通電
    await initializeChatData();
  } else {
    // 💡 核心修正：如果現在還沒有（正在登入中），我們就佈下眼線監聽它！
    console.log("[熱啟動] 暫時未取得登入身分，已佈設狀態監聽哨...");
    
    const unwatch = watch(() => chatStore.currentUserId, async (newId) => {
      if (newId) {
        await initializeChatData();
        unwatch(); // 順利通電後，把監聽器註銷掉，釋放記憶體
      }
    });
  }
});


// 註銷全域變數，防止記憶體洩漏
onUnmounted(() => {
  if (window.__triggerApprovalModal) {
    try {
      window.__triggerApprovalModal = null;
    } catch(e) {
      delete window.__triggerApprovalModal;
    }
  }
  window.removeEventListener('hermes-approval-required', handleGlobalApprovalSignal);
  
  // 離開聊天室時大掃除
  chatStore.logoutUserAction();
});





</script>


<style scoped>
/* 0. 淡藍色科技感底色：取代原本純灰平面背景 */
.tech-bg {
  background:
    radial-gradient(circle at 0% 0%, rgba(56, 189, 248, 0.10), transparent 40%),
    radial-gradient(circle at 100% 100%, rgba(14, 165, 233, 0.08), transparent 40%),
    #f6fbff;
}

/* 1. 您原本舊有的高質感 RAG 文本與藍色膠囊防禦樣式 */
.white-space-pre-wrap { white-space: pre-wrap; }
.scrollbar-thin::-webkit-scrollbar { height: 4px; }
.scrollbar-thin::-webkit-scrollbar-thumb { background: #e5e7eb; border-radius: 10px; }

/* 2. 確保自訂專家 Prompt 的「兩行省略號」完美卡位 */
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 3. 微軟/Dify 風格懸停陰影 */
.shadow-3xs {
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.03), 0 1px 6px -1px rgba(0, 0, 0, 0.02);
}

/* ========================================================================= */
/* ⚠️ 任務三全新新增：協同審查凍結與動畫樣式 */
/* ========================================================================= */

/* 彈窗深層客製化：強行覆蓋圓角與超級大投影 */
:deep(.approval-dialog) {
  border-radius: 1rem !important;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25) !important;
  overflow: hidden;
}

/* 當審查被阻斷時，透過 pointer-events-none 防止使用者點擊對話視窗任何物件 */
.pointer-events-none {
  pointer-events: none;
}

/* 思考氣泡與新對話載入時的平滑淡入動畫 */
.animate-fade-in {
  animation: fadeIn 0.35s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

@keyframes fadeIn {
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

