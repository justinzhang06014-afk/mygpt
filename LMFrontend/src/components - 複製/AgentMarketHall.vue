<template>
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
    <div class="max-w-5xl mx-auto">
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        
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

          <!-- 🎯 物理大掃除按鈕：阻斷冒泡防止誤進房間 -->
          <div class="flex justify-end items-center mt-1 border-t border-[#f9fafb] pt-2">
            <el-button 
              type="danger" 
              size="small" 
              link
              icon="Delete"
              :loading="isDeletingLock"
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

  <!-- 🛠️ 【捏造全新大腦助理】彈窗 -->
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
          placeholder="自訂此專家的性格與回覆偏好。" 
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
import { ref } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';

// 接收由主控官傳遞進來的核心 Pinia Store
defineProps({
  chatStore: {
    type: Object,
    required: true
  }
});

// =========================================================================
// ✨ 狀態變數與事件處理
// =========================================================================
const createAgentDialogVisible = ref(false);
const newAgentName = ref('');
const newAgentPrompt = ref('');
const isCreatingAgent = ref(false);
const isDeletingLock = ref(false); // 銷毀防抖鎖

// 打開大廳的「捏造助理」彈窗
const handleOpenCreateAgentDialog = () => {
  newAgentName.value = '';
  newAgentPrompt.value = '';
  createAgentDialogVisible.value = true;
};

// 提交大腦捏造：呼叫 POST /api/agents 端點
const submitCreateCustomAgent = async () => {
  if (!newAgentName.value.trim()) {
    ElMessage.warning('請輸入助手專屬功能稱呼！');
    return;
  }

  try {
    isCreatingAgent.value = true;
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

// 誅 Agent 九族彈窗警告
const handleDeleteAgent = (incomingId) => {
  if (isDeletingLock.value) return;

  let realAgentId = incomingId;
  if (typeof incomingId === 'number' && chatStore.agents) {
    const found = chatStore.agents.find(a => a.id === incomingId);
    if (found) realAgentId = found.agent_id || found.agentId;
  }
  
  if (!realAgentId) return;

  ElMessageBox.confirm(
    '此操作將連同該專家大腦、其底下所有房間對話，以及硬碟實體長期記憶檔案一併徹底永久銷毀，確定執行物理抄家？',
    '🚨 終極銷毀警告',
    {
      confirmButtonText: '確定要誅Agent九族嗎',
      cancelButtonText: '取消',
      type: 'warning',
      distinguishCancelAndClose: true,
      customClass: 'rounded-2xl'
    }
  ).then(() => {
    executePhysicalDelete(realAgentId);
  }).catch((action) => {
    console.log("[大廳偵錯] 彈窗取消行動代碼:", action);
  });
};

// 背景實體刪除執行函數
const executePhysicalDelete = async (agentId) => {
  try {
    isDeletingLock.value = true;
    const success = await chatStore.deleteAgentAction(agentId);
    if (success) {
      ElMessage({ type: 'success', message: '該 AI 專家大腦及實體磁碟日記已安全回歸塵土！' });
    } else {
      ElMessage({ type: 'error', message: '資料庫或實體硬碟大掃除發生錯誤。' });
    }
  } catch (err) {
    console.error("[大廳抄家線] 執行崩潰:", err);
  } finally {
    isDeletingLock.value = false;
  }
};
</script>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.shadow-3xs {
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.03), 0 1px 6px -1px rgba(0, 0, 0, 0.02);
}
</style>
