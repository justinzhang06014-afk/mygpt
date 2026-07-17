<!-- src/components/SkillPendingReviewModal.vue -->
<template>
  <el-dialog
    v-model="visible"
    fullscreen
    class="pending-review-dialog"
    @open="loadPending"
  >
    <template #header>
      <div class="pending-header">
        <span class="pending-icon">🗂️</span>
        <div>
          <h1>Skill 待審核清單</h1>
          <p>當這個 Agent 的 <code>skills.write_approval</code> 開啟後，hermes 建立/修改技能檔案時會先暫存在這裡，等你核准或拒絕才會真的落盤</p>
        </div>
      </div>
    </template>

    <div class="pending-body">
      <div v-if="isLoading" class="state-block">
        <el-icon class="is-loading spin-icon"><Loading /></el-icon>
        <p>正在讀取待審核清單…</p>
      </div>

      <div v-else-if="errorMsg" class="state-block error-block">
        <span class="state-icon">❌</span>
        <p>{{ errorMsg }}</p>
      </div>

      <div v-else-if="pendingList.length === 0" class="state-block safe-block">
        <span class="state-icon">✅</span>
        <p>目前沒有待審核的技能寫入</p>
      </div>

      <div v-else class="pending-grid">
        <div v-for="item in pendingList" :key="item.id" class="pending-card">
          <div class="pending-top">
            <span class="pending-action">{{ actionLabel(item.action) }}</span>
            <span class="pending-time">{{ formatTime(item.created_at) }}</span>
          </div>
          <p class="pending-summary">{{ item.summary || '（無摘要）' }}</p>
          <p class="pending-meta">來源: {{ item.origin === 'background_review' ? '背景自我審視' : '前景對話' }} · ID: {{ item.id }}</p>
          <div class="pending-actions">
            <el-button
              size="small"
              type="primary"
              :loading="actingId === item.id && actingType === 'approve'"
              :disabled="actingId === item.id"
              @click="handleApprove(item)"
            >
              ✅ 核准並套用
            </el-button>
            <el-button
              size="small"
              type="danger"
              plain
              :loading="actingId === item.id && actingType === 'reject'"
              :disabled="actingId === item.id"
              @click="handleReject(item)"
            >
              🗑️ 拒絕
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="pending-footer">
        <el-button @click="visible = false">關閉</el-button>
        <el-button type="primary" :loading="isLoading" @click="loadPending">🔄 重新整理</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref } from 'vue';
import { useChatStore } from '../stores/chat';
import { ElMessage } from 'element-plus';
import { Loading } from '@element-plus/icons-vue';

const chatStore = useChatStore();
const visible = defineModel({ type: Boolean, default: false });

const isLoading = ref(false);
const errorMsg = ref('');
const pendingList = ref([]);
const actingId = ref('');
const actingType = ref('');

const actionLabel = (action) => {
  const map = {
    create: '📝 建立新技能',
    edit: '✏️ 編輯技能',
    patch: '🩹 局部修改',
    write_file: '📄 寫入檔案',
    delete: '🗑️ 刪除',
    remove_file: '🗑️ 移除檔案',
  };
  return map[action] || action || '未知操作';
};

const formatTime = (unixSeconds) => {
  if (!unixSeconds) return '';
  return new Date(unixSeconds * 1000).toLocaleString();
};

const loadPending = async () => {
  if (!chatStore.currentAgentId) {
    errorMsg.value = '目前不在任何 Agent 的辦公室中，無法查看待審核清單。';
    return;
  }
  isLoading.value = true;
  errorMsg.value = '';
  try {
    pendingList.value = await chatStore.listPendingSkillWritesAction(chatStore.currentAgentId);
  } catch (err) {
    console.error('讀取待審核清單失敗:', err);
    errorMsg.value = err?.response?.data?.error || err?.message || '未知錯誤';
  } finally {
    isLoading.value = false;
  }
};

const handleApprove = async (item) => {
  actingId.value = item.id;
  actingType.value = 'approve';
  try {
    const result = await chatStore.approvePendingSkillWriteAction(chatStore.currentAgentId, item.id);
    if (result?.applied) {
      ElMessage.success(`✅ 已核准並套用：${item.summary || item.id}`);
      pendingList.value = pendingList.value.filter((p) => p.id !== item.id);
    } else {
      ElMessage.error(`核准失敗：${result?.detail?.error || '未知原因，項目仍保留在待審核清單'}`);
    }
  } catch (err) {
    console.error('核准失敗:', err);
    ElMessage.error(`核准失敗：${err?.response?.data?.error || err?.message || '未知錯誤'}`);
  } finally {
    actingId.value = '';
    actingType.value = '';
  }
};

const handleReject = async (item) => {
  actingId.value = item.id;
  actingType.value = 'reject';
  try {
    await chatStore.rejectPendingSkillWriteAction(chatStore.currentAgentId, item.id);
    ElMessage.success(`🗑️ 已拒絕：${item.summary || item.id}`);
    pendingList.value = pendingList.value.filter((p) => p.id !== item.id);
  } catch (err) {
    console.error('拒絕失敗:', err);
    ElMessage.error(`拒絕失敗：${err?.response?.data?.error || err?.message || '未知錯誤'}`);
  } finally {
    actingId.value = '';
    actingType.value = '';
  }
};
</script>

<style scoped>
:deep(.pending-review-dialog) {
  background:
    radial-gradient(circle at 10% 0%, rgba(56, 189, 248, 0.12), transparent 45%),
    radial-gradient(circle at 90% 100%, rgba(14, 165, 233, 0.10), transparent 45%),
    #f8fcff;
}
:deep(.el-dialog__header) {
  padding: 0 !important;
  margin: 0 !important;
  border-bottom: 1px solid #e0f2fe;
}

.pending-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 22px 32px;
  background: linear-gradient(135deg, #eafaff 0%, #f5fbff 60%, #ffffff 100%);
}
.pending-icon {
  font-size: 34px;
  filter: drop-shadow(0 0 12px rgba(14, 165, 233, 0.35));
}
.pending-header h1 {
  font-size: 20px;
  font-weight: 800;
  color: #0c4a6e;
  margin: 0;
}
.pending-header p {
  font-size: 12px;
  color: #64748b;
  margin: 2px 0 0;
}
.pending-header code {
  background: #e0f2fe;
  color: #0369a1;
  padding: 1px 6px;
  border-radius: 6px;
}

.pending-body {
  max-width: 960px;
  margin: 0 auto;
  padding: 32px;
}

.state-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 100px 0;
  color: #94a3b8;
}
.spin-icon { font-size: 36px; color: #0ea5e9; }
.state-icon { font-size: 44px; }
.error-block { color: #dc2626; }
.safe-block { color: #059669; padding: 60px 0; }

.pending-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.pending-card {
  background: white;
  border: 1px solid #e0f2fe;
  border-radius: 14px;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.pending-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.pending-action { font-weight: 700; font-size: 14px; color: #0c4a6e; }
.pending-time { font-size: 11px; color: #94a3b8; }
.pending-summary { font-size: 13px; color: #334155; margin: 4px 0; }
.pending-meta { font-size: 11px; color: #94a3b8; }
.pending-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.pending-footer {
  display: flex;
  justify-content: center;
  gap: 12px;
  padding: 16px;
}
</style>
