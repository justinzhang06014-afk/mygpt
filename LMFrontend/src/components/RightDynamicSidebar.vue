<!-- src/components/RightDynamicSidebar.vue -->
<template>
  <div class="right-dynamic-sidebar flex h-full bg-white border-l border-[#e0f2fe] w-[440px] shrink-0 overflow-hidden shadow-2xs">

    <!-- 🎛️ 左小欄：黃金垂直導航工具列 -->
    <div class="sidebar-tabs-bar w-14 border-r border-[#f0f9ff] flex flex-col items-center py-5 gap-5 bg-[#f8fcff]">
      <button
        type="button"
        @click="activeTab = 'memory'"
        class="w-10 h-10 rounded-xl flex flex-col items-center justify-center text-lg transition-all relative group"
        :class="activeTab === 'memory' ? 'bg-[#e0f2fe] text-[#0284c7] border border-[#7dd3fc] font-bold shadow-xs' : 'text-[#94a3b8] hover:bg-[#f0f9ff] hover:text-[#1f2937]'"
      >
        <span>🧠</span>
      </button>

      <button
        type="button"
        @click="activeTab = 'skill'"
        class="w-10 h-10 rounded-xl flex flex-col items-center justify-center text-lg transition-all relative group"
        :class="activeTab === 'skill' ? 'bg-[#e0f2fe] text-[#0284c7] border border-[#7dd3fc] font-bold shadow-xs' : 'text-[#94a3b8] hover:bg-[#f0f9ff] hover:text-[#1f2937]'"
      >
        <span>⚡</span>
      </button>
    </div>

    <!-- 📺 右大欄：動態多功能展示主體 -->
    <div class="sidebar-main-content flex-1 flex flex-col h-full overflow-hidden bg-[#fbfeff]">

      <!-- 統一提取的頂部公共 Header -->
      <div class="panel-header py-4 px-5 border-b border-[#f0f9ff] flex items-center justify-between bg-white shadow-3xs gap-2">
        <div class="flex items-center gap-2 min-w-0">
          <span class="text-xl shrink-0">{{ activeTab === 'memory' ? '🧠' : '⚡' }}</span>
          <h2 class="text-sm font-bold text-[#0c4a6e] tracking-wide truncate">
            {{ displayAgentName }} ── {{ activeTab === 'memory' ? '記憶硬碟' : '外掛技能鏈' }}
          </h2>
        </div>

        <div v-if="activeTab === 'skill'" class="flex items-center gap-2 shrink-0">
          <el-dropdown trigger="click" @command="handleExport">
            <el-button type="primary" size="small" plain round :loading="isExporting">
              📤 匯出
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="hermes">hermes 原生格式 (.tar.gz)</el-dropdown-item>
                <el-dropdown-item command="zip">壓縮檔 (.zip)</el-dropdown-item>
                <el-dropdown-item command="skill">Skill 標準格式 (.md)</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>

          <el-button type="success" size="small" plain round @click="importModalVisible = true">
            📥 匯入技能
          </el-button>
        </div>
      </div>

      <!-- 核心多視窗調度區 -->
      <div class="flex-1 overflow-hidden">
        <AgentMemoryPanel v-if="activeTab === 'memory'" />

        <!-- ⚡ Skill 分頁：不再塞進去一堆假開關,改成大商城與安全掃描的入口 -->
        <div v-else class="flex flex-col h-full p-5 gap-4 bg-[#fbfeff]">
          <button type="button" class="market-entry-card" @click="marketVisible = true">
            <div class="market-entry-icon">🛒</div>
            <div class="market-entry-text">
              <h3>前往 Skill 商城</h3>
              <p>搜尋並安裝 hermes 官方市集的 8 萬多個真實技能</p>
            </div>
            <span class="market-entry-arrow">→</span>
          </button>

          <button type="button" class="market-entry-card" @click="mcpMarketVisible = true">
            <div class="market-entry-icon">🔌</div>
            <div class="market-entry-text">
              <h3>前往 MCP 商店</h3>
              <p>設定這個 Agent 要常駐/選配安裝哪些 MCP 工具</p>
            </div>
            <span class="market-entry-arrow">→</span>
          </button>

          <button type="button" class="security-entry-card" @click="securityModalVisible = true">
            <div class="security-entry-icon">🛡️</div>
            <div class="market-entry-text">
              <h3>供應鏈安全掃描</h3>
              <p>即時執行 hermes security audit，查詢 OSV.dev 已知漏洞</p>
            </div>
            <span class="market-entry-arrow">→</span>
          </button>

          <button type="button" class="security-entry-card" @click="pendingReviewModalVisible = true">
            <div class="security-entry-icon">🗂️</div>
            <div class="market-entry-text">
              <h3>Skill 待審核清單</h3>
              <p>檢視並核准／拒絕 hermes 暫存的技能檔案異動</p>
            </div>
            <span class="market-entry-arrow">→</span>
          </button>
        </div>
      </div>

    </div>

    <ImportSkillModal v-model="importModalVisible" />
    <SecurityAuditModal v-model="securityModalVisible" />
    <SkillMarketplaceView v-model="marketVisible" />
    <SkillPendingReviewModal v-model="pendingReviewModalVisible" />
    <McpMarketplaceView v-model="mcpMarketVisible" />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { useChatStore } from '../stores/chat';
import { ElMessage } from 'element-plus';
import AgentMemoryPanel from './AgentMemoryPanel.vue';
import ImportSkillModal from './ImportSkillModal.vue';
import SecurityAuditModal from './SecurityAuditModal.vue';
import SkillMarketplaceView from './SkillMarketplaceView.vue';
import SkillPendingReviewModal from './SkillPendingReviewModal.vue';
import McpMarketplaceView from './McpMarketplaceView.vue';

const chatStore = useChatStore();
const activeTab = ref('memory');
const isExporting = ref(false);
const importModalVisible = ref(false);
const securityModalVisible = ref(false);
const marketVisible = ref(false);
const pendingReviewModalVisible = ref(false);
const mcpMarketVisible = ref(false);

const handleExport = async (format) => {
  if (!chatStore.currentAgentId) {
    ElMessage.warning('目前不在任何 Agent 的辦公室中，無法匯出。');
    return;
  }
  try {
    isExporting.value = true;
    await chatStore.exportAgentAction(chatStore.currentAgentId, format);
    ElMessage.success('📤 匯出成功，檔案已開始下載。');
  } catch (err) {
    console.error('匯出 Agent 失敗:', err);
    ElMessage.error(`匯出失敗：${err?.response?.data?.error || err?.message || '未知錯誤'}`);
  } finally {
    isExporting.value = false;
  }
};

// =========================================================================
// 🔒 【實體硬碟快取鎖】displayAgentName 標題時序補償器
// =========================================================================
const displayAgentName = computed(() => {
  if (chatStore.currentAgent?.name) {
    return chatStore.currentAgent.name;
  }

  const savedName = localStorage.getItem('CORE_CURRENT_AGENT_NAME');
  if (savedName) {
    return savedName;
  }

  return "🤖 運作中的專家助理";
});
</script>

<style scoped>
.market-entry-card, .security-entry-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  border-radius: 18px;
  border: 1px solid #bae6fd;
  background: linear-gradient(135deg, #f0f9ff 0%, #ffffff 100%);
  cursor: pointer;
  text-align: left;
  transition: all 0.2s ease;
}
.market-entry-card:hover, .security-entry-card:hover {
  border-color: #38bdf8;
  box-shadow: 0 12px 28px -16px rgba(14, 165, 233, 0.5);
  transform: translateY(-2px);
}
.market-entry-icon, .security-entry-icon {
  font-size: 28px;
  width: 52px;
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  background: white;
  border: 1px solid #e0f2fe;
  flex-shrink: 0;
}
.market-entry-text { flex: 1; min-width: 0; }
.market-entry-text h3 {
  font-size: 14px;
  font-weight: 700;
  color: #0c4a6e;
  margin: 0 0 2px;
}
.market-entry-text p {
  font-size: 11px;
  color: #64748b;
  margin: 0;
  line-height: 1.4;
}
.market-entry-arrow {
  color: #38bdf8;
  font-size: 18px;
  font-weight: 700;
  flex-shrink: 0;
}
</style>
