<!-- src/components/ForkAgentModal.vue -->
<template>
  <el-dialog
    v-model="visible"
    title="🧬 複製新 Agent"
    width="440px"
    :close-on-click-modal="false"
    append-to-body
    class="fork-agent-dialog rounded-2xl shadow-2xl"
    @open="handleModalOpen"
  >
    <div class="fork-modal-content flex flex-col gap-5 py-2">
      <!-- 頂部高質感引導說明 -->
      <div class="bg-[#f0f7ff] border border-[#d6e4ff] p-4 rounded-xl flex gap-3 items-start">
        <span class="text-2xl mt-0.5">💡</span>
        <p class="text-xs text-[#1d39c4] leading-relaxed">
          以現有的 AI 專家大腦為範本，透過 hermes 原生指令 <code>profile create --clone-from</code> 長出一個全新的獨立 Agent，完整繼承範本的人設、記憶與技能，之後彼此各自獨立發展、互不影響。
        </p>
      </div>

      <!-- 表單本體 -->
      <el-form label-position="top" class="fork-form">
        <!-- 1. 下拉選單：選擇來源 Agent 範本 -->
        <el-form-item label="📂 請選擇複製範本 Agent" required>
          <el-select
            v-model="sourceAgentId"
            placeholder="請選擇一個現有的專家助理..."
            class="w-full !rounded-xl"
            size="default"
            filterable
          >
            <el-option
              v-for="agent in localAvailableAgents"
              :key="agent.id"
              :label="`${agent.name}`"
              :value="agent.id"
            />
          </el-select>
          <p class="text-[11px] text-[#9ca3af] mt-1.5">
            * 範本 Agent 必須已經對話過至少一次(已初始化 hermes profile)才能作為複製來源。
          </p>
        </el-form-item>

        <!-- 2. 新 Agent 名稱 -->
        <el-form-item label="✨ 新 Agent 名稱" required>
          <el-input
            v-model="newAgentName"
            placeholder="請輸入這個新誕生助理的名稱..."
            class="w-full !rounded-xl"
          />
        </el-form-item>
      </el-form>
    </div>

    <!-- 彈窗尾部控制鈕 -->
    <template #footer>
      <div class="flex justify-end gap-2 border-t border-[#f3f4f6] pt-4">
        <el-button @click="visible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="isSubmitting"
          :disabled="!sourceAgentId || !newAgentName.trim()"
          @click="submitForkExecute"
        >
          🧬 啟動複製
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref } from 'vue';
import { useChatStore } from '../stores/chat';
import { ElMessage } from 'element-plus';

const chatStore = useChatStore();

const visible = defineModel({ type: Boolean, default: false });
// 由呼叫方(ChatRoom.vue 的 Agent 卡片)預先帶入要複製的來源 Agent
const props = defineProps({
  presetSourceAgentId: { type: String, default: '' }
});

const sourceAgentId = ref('');
const newAgentName = ref('');
const isSubmitting = ref(false);

// 宣告內部完全隔離的清洗名單
const localAvailableAgents = ref([]);

// =========================================================================
// 🔄 【大小寫一網打盡】彈窗喚醒數據清洗函數
// =========================================================================
const handleModalOpen = async () => {
  // 1. 狀態重置
  sourceAgentId.value = props.presetSourceAgentId || '';
  newAgentName.value = '';
  localAvailableAgents.value = [];

  // 2. 刷新後端名冊
  try {
    if (typeof chatStore.fetchAvailableForkAgents === 'function') {
      await chatStore.fetchAvailableForkAgents();
    } else if (typeof chatStore.fetchAgentsAction === 'function') {
      await chatStore.fetchAgentsAction();
    }
  } catch (err) {
    console.error("拉取最新名冊失敗:", err);
  }

  // 3. 🛡️ 【唯一金鑰鎖】：只認 agent_id，絕對不碰、不讀、不看流水號 id
  const uniqueMap = new Map();
  const rawAgents = chatStore.agents || [];

  rawAgents.forEach(a => {
    const agentId = a.agent_id || a.AgentId || a.agentId;
    const name = a.name || a.Name;

    if (agentId && name) {
       const idStr = String(agentId).trim();
       uniqueMap.set(idStr.toLowerCase(), { originalId: idStr, name: String(name).trim() });
    }
  });

  // 4. 轉換為選單陣列
  localAvailableAgents.value = Array.from(uniqueMap.values()).map(data => ({
    id: data.originalId,
    name: data.name
  }));
};


// =========================================================================
// 🚀 真．複製執行函數
// =========================================================================
const submitForkExecute = async () => {
  const sourceId = sourceAgentId.value;
  const name = newAgentName.value.trim();

  if (!sourceId) {
    ElMessage.warning('請選擇一個現有的專家助理作為複製範本！');
    return;
  }
  if (!name) {
    ElMessage.warning('請輸入新 Agent 的名稱！');
    return;
  }

  const sourceAgent = localAvailableAgents.value.find(a => a.id === sourceId);
  const inheritedPrompt = chatStore.agents.find(a => (a.agent_id || a.AgentId) === sourceId)?.system_prompt
    || chatStore.agents.find(a => (a.agent_id || a.AgentId) === sourceId)?.SystemPrompt
    || `你是一位專業的${name}。請盡可能提供精準、客觀且具備深度的分析。`;

  try {
    isSubmitting.value = true;
    await chatStore.cloneAgentAction(name, inheritedPrompt, sourceId);
    ElMessage.success(`🎉 複製成功！「${name}」已誕生，完整繼承「${sourceAgent?.name || sourceId}」的記憶與技能。`);
    visible.value = false;
  } catch (err) {
    console.error('❌ 後端複製執行失敗:', err);
    const detail = err?.response?.data?.error || err?.message || '未知錯誤';
    ElMessage.error(`複製失敗：${detail}`);
  } finally {
    isSubmitting.value = false;
  }
};
</script>

<style scoped>
:deep(.fork-agent-dialog) {
  border-radius: 1rem !important;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.3) !important;
  overflow: hidden;
}
:deep(.el-form-item__label) {
  font-weight: 600 !important;
  color: #374151 !important;
  font-size: 13px !important;
  padding-bottom: 6px !important;
}
</style>
