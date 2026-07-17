<!-- src/components/AgentMemoryPanel.vue -->
<template>
  <!-- 💡 降級改造：移除最頂部的 panel-header，使其成為專注於渲染記憶 facts 的乾淨子組件 -->
  <div class="agent-memory-sub-panel flex flex-col h-full bg-[#fcfdfe] overflow-hidden animate-fade-in">
    
    <!-- 第一層：頂部「大軌道」雙切換藥丸鈕 (Pill Tabs) -->
    <div class="track-selector-wrapper p-4 bg-white border-b border-[#f9fafb]">
      <div class="flex bg-[#f3f4f6] p-1 rounded-xl justify-stretch gap-1">
        <button 
          type="button"
          class="flex-1 py-2 text-sm font-semibold rounded-lg transition-all duration-200 flex items-center justify-center gap-1.5"
          :class="currentTrack === 'memory' ? 'bg-white text-[#67c23a] shadow-xs' : 'text-[#6b7280] hover:text-[#1f2937]'"
          @click="handleTrackChange('memory')"
        >
          <span>🧠</span> 智慧體知識
        </button>
        <button 
          type="button"
          class="flex-1 py-2 text-sm font-semibold rounded-lg transition-all duration-200 flex items-center justify-center gap-1.5"
          :class="currentTrack === 'user' ? 'bg-white text-[#409eff] shadow-xs' : 'text-[#6b7280] hover:text-[#1f2937]'"
          @click="handleTrackChange('user')"
        >
          <span>👤</span> 用戶偏好
        </button>
      </div>
    </div>

    <!-- 📊 動態腦飽和度進度條 (ProgressBar 與視覺防禦變色) -->
    <div class="saturation-wrapper px-5 py-3.5 bg-white border-b border-[#f3f4f6]">
      <div class="flex items-center justify-between text-xs font-medium mb-1.5">
        <span class="text-[#4b5563]">大腦記憶飽和度</span>
        <span :class="isSaturationWarning ? 'text-[#ef4444] font-bold animate-pulse' : 'text-[#9ca3af]'">
          {{ saturationPercentage }}%
        </span>
      </div>
      
      <div class="w-full bg-[#e5e7eb] h-2 rounded-full overflow-hidden">
        <div 
          class="h-full transition-all duration-500 ease-out rounded-full"
          :class="isSaturationWarning ? 'bg-gradient-to-r from-[#f56c6c] to-[#f56c6c]' : (currentTrack === 'memory' ? 'bg-[#67c23a]' : 'bg-[#409eff]')"
          :style="{ width: `${saturationPercentage}%` }"
        ></div>
      </div>

      <p v-if="isSaturationWarning" class="text-[11px] text-[#f56c6c] mt-1.5 flex items-center gap-1 font-medium">
        <span>⚠️</span> 記憶即將飽和，請及時清理或銷毀舊資料！
      </p>
    </div>

    <!-- 📜 記憶事實卡片清單 (Fact Cards) 流：純樸平面顯示，hermes 本身沒有分類概念，不再假裝分類 -->
    <el-scrollbar class="flex-1 p-4 bg-[#f8fafc]">
      <div class="flex flex-col gap-3">
        <div
          v-for="item in currentMemories"
          :key="item.id"
          class="fact-card bg-white border border-[#e5e7eb] p-3.5 rounded-xl shadow-3xs relative group hover:border-gray-300 transition-all duration-150 animate-fade-in"
        >
          <button 
            type="button"
            class="absolute top-2 right-2 text-[#9ca3af] hover:text-[#f56c6c] opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded-md hover:bg-[#fef2f2]"
            title="銷毀此條記憶事實"
            @click="handleDeleteFact(item.id)"
          >
            <el-icon size="14"><Delete /></el-icon>
          </button>

          <p class="text-sm text-[#374151] leading-relaxed white-space-pre-wrap pr-5">
            {{ item.text }}
          </p>
        </div>

        <div v-if="currentMemories.length === 0" class="flex flex-col items-center justify-center py-16 text-[#9ca3af] gap-2">
          <span class="text-3xl">🕳️</span>
          <p class="text-xs">尚未封存任何長期記憶事實。</p>
        </div>
      </div>
    </el-scrollbar>

    <!-- ✍️ 底部「🧠 記住這句話」手動強制灌輸區 -->
    <div class="injection-wrapper p-4 bg-white border-t border-[#e5e7eb]">
      <div class="flex gap-2">
        <el-input
          v-model="bulkInputText"
          placeholder="手動強制灌輸：如『使用者不喜歡被打擾』"
          size="default"
          clearable
          @keyup.enter="handleInjectMemory"
        />
        <el-button 
          :type="currentTrack === 'memory' ? 'success' : 'primary'"
          size="default"
          :loading="isInjecting"
          @click="handleInjectMemory"
        >
          灌輸
        </el-button>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { useChatStore } from '../stores/chat';
import { Delete } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';

const chatStore = useChatStore();
const activeSubTab = ref('');
const currentTrack = ref('memory');      
const bulkInputText = ref('');          
const isInjecting = ref(false);         

const currentPackage = computed(() => {
  return currentTrack.value === 'memory' ? chatStore.memoryPackage : chatStore.userPackage;
});

const saturationPercentage = computed(() => {
  if (!currentPackage.value?.meta) return 0;
  return currentPackage.value.meta.brain_saturation_percentage || 0;
});

const isSaturationWarning = computed(() => {
  return saturationPercentage.value >= 85;
});

const currentMemories = computed(() => currentPackage.value?.memories || []);

const refreshPanelData = async () => {
  const agentId = chatStore.currentAgentId;
  if (!agentId) return;

  try {
    await chatStore.fetchAgentMemories(agentId, currentTrack.value);
  } catch (err) {
    if (err.response && err.response.status === 500) {
      console.warn(`[記憶面板安全自癒] 冷啟動降級防禦啟動。`);
      const fallbackPackage = { meta: { brain_saturation_percentage: 0 }, categories: [], memories: [] };
      if (currentTrack.value === 'memory') {
        chatStore.memoryPackage = fallbackPackage;
      } else {
        chatStore.userPackage = fallbackPackage;
      }
    } else {
      console.error('[記憶面板] 通訊崩潰:', err);
    }
  }
};

const handleTrackChange = (trackType) => {
  currentTrack.value = trackType;
  activeSubTab.value = ''; 
  refreshPanelData();
};

watch(() => chatStore.currentAgentId, (newAgentId) => {
  if (newAgentId) {
    activeSubTab.value = '';
    refreshPanelData();
  }
}, { immediate: true });

const handleDeleteFact = async (factId) => {
  const agentId = chatStore.currentAgentId;
  if (!agentId || !factId) return;

  try {
    await chatStore.deleteSpecificFact(agentId, currentTrack.value, factId);
    ElMessage.success('🗑️ 該條長期記憶片段已當場銷毀！');
    await refreshPanelData(); 
  } catch (err) {
    console.error('銷毀事實失敗:', err);
  }
};

const handleInjectMemory = async () => {
  const agentId = chatStore.currentAgentId;
  if (!agentId) return;
  if (!bulkInputText.value.trim()) return;

  try {
    isInjecting.value = true;
    await chatStore.importBulkMemories(agentId, currentTrack.value, [bulkInputText.value.trim()]);
    ElMessage.success('🧠 記憶強行灌輸成功！');
    bulkInputText.value = ''; 
    await refreshPanelData(); 
  } catch (err) {
    console.error('強制灌輸失敗:', err);
  } finally {
    isInjecting.value = false;
  }
};

onMounted(() => {
  refreshPanelData();
});
</script>

<style scoped>
.animate-fade-in {
  animation: fadeIn 0.25s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateX(6px); }
  to { opacity: 1; transform: translateX(0); }
}
</style>
