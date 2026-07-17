<!-- src/components/McpMarketplaceView.vue -->
<template>
  <el-dialog
    v-model="visible"
    fullscreen
    :show-close="true"
    class="mcp-market-dialog"
    @open="handleOpen"
  >
    <template #header>
      <div class="market-header">
        <div class="market-title">
          <span class="market-icon">🔌</span>
          <div>
            <h1>MCP 商店</h1>
            <p>管理這個 Agent 要用哪些 MCP 工具，常駐的一律開機就裝好，選配的要用再裝</p>
          </div>
        </div>

        <div class="market-agent-picker">
          <span class="picker-label">設定對象</span>
          <el-select v-model="targetAgentId" placeholder="選擇 Agent" class="agent-select" filterable>
            <el-option v-for="agent in agentOptions" :key="agent.id" :label="agent.name" :value="agent.id" />
          </el-select>
        </div>
      </div>
    </template>

    <div class="market-body">
      <div v-if="isLoading" class="empty-state">
        <el-icon class="is-loading spin-icon"><Loading /></el-icon>
        <p>正在讀取 MCP 目錄…</p>
      </div>

      <div v-else-if="!targetAgentId" class="empty-state">
        <span class="empty-icon">🧭</span>
        <p>請先選擇要設定的 Agent</p>
      </div>

      <div v-else-if="cards.length === 0" class="empty-state">
        <span class="empty-icon">🔭</span>
        <p>母版目錄目前是空的，請管理員先新增 MCP</p>
      </div>

      <div v-else class="results-grid">
        <div v-for="card in cards" :key="card.name" class="mcp-card">
          <div class="mcp-card-top">
            <span class="mcp-name">{{ card.displayName || card.name }}</span>
            <span class="status-dot" :class="card.needsCredentials ? (card.configured ? 'dot-green' : 'dot-red') : 'dot-neutral'">
              {{ card.needsCredentials ? (card.configured ? '● 已設定 API' : '● 未設定 API') : '● 免設定' }}
            </span>
          </div>
          <p class="mcp-desc">{{ card.description }}</p>

          <div class="mcp-badges">
            <span v-if="card.selection === 'resident'" class="sel-badge sel-resident">常駐中</span>
            <span v-else-if="card.selection === 'optional_installed'" class="sel-badge sel-optional">已安裝（選配）</span>
          </div>

          <div v-if="card.credentialFields?.length" class="cred-form">
            <div v-for="field in card.credentialFields" :key="field.key" class="cred-field">
              <label>{{ field.label }}{{ field.required ? ' *' : '' }}</label>
              <el-input
                v-model="credentialDrafts[card.name][field.key]"
                :type="field.type === 'password' ? 'password' : 'text'"
                size="small"
                show-password
                :placeholder="field.required ? '必填' : '可留空'"
              />
            </div>
            <el-button size="small" class="save-cred-btn" :loading="savingCredId === card.name" @click="handleSaveCredentials(card)">
              💾 儲存憑證
            </el-button>
          </div>

          <div class="mcp-card-bottom">
            <el-button
              size="small"
              :type="card.selection === 'resident' ? 'default' : 'primary'"
              :loading="togglingId === card.name + ':resident'"
              @click="handleToggleSelection(card, card.selection === 'resident' ? null : 'resident')"
            >
              {{ card.selection === 'resident' ? '取消常駐' : '📌 設為常駐' }}
            </el-button>
            <el-button
              size="small"
              :type="card.selection === 'optional_installed' ? 'default' : 'success'"
              :loading="togglingId === card.name + ':optional'"
              @click="handleToggleSelection(card, card.selection === 'optional_installed' ? null : 'optional_installed')"
            >
              {{ card.selection === 'optional_installed' ? '移除' : '➕ 加入（選配）' }}
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, computed, reactive } from 'vue';
import { useChatStore } from '../stores/chat';
import { ElMessage } from 'element-plus';
import { Loading } from '@element-plus/icons-vue';

const chatStore = useChatStore();
const visible = defineModel({ type: Boolean, default: false });

const isLoading = ref(false);
const targetAgentId = ref('');
const catalog = ref({});       // 母版：{ name: {displayName, description, credentialFields, ...} }
const agentServers = ref({});  // 這個 agent 目前的狀態：{ name: {selection, credentialsConfigured} }
const credentialDrafts = reactive({}); // 每張卡片正在編輯中的憑證輸入值
const togglingId = ref('');
const savingCredId = ref('');

const agentOptions = computed(() => (chatStore.agents || []).map(a => ({
  id: a.agent_id || a.AgentId,
  name: a.name || a.Name
})));

const cards = computed(() => {
  return Object.entries(catalog.value).map(([name, meta]) => {
    const agentEntry = agentServers.value[name] || {};
    const credentialFields = meta.credentialFields || [];
    const requiredKeys = credentialFields.filter(f => f.required).map(f => f.key);
    const configured = requiredKeys.length === 0
      ? true
      : requiredKeys.every(k => agentEntry.credentialsConfigured?.[k]);
    return {
      name,
      displayName: meta.displayName,
      description: meta.description,
      credentialFields,
      needsCredentials: credentialFields.length > 0,
      configured,
      selection: agentEntry.selection ?? null
    };
  });
});

const ensureDraft = (name, fields) => {
  if (!credentialDrafts[name]) {
    credentialDrafts[name] = {};
    for (const f of fields) credentialDrafts[name][f.key] = '';
  }
};

const handleOpen = async () => {
  if (!targetAgentId.value) {
    targetAgentId.value = chatStore.currentAgentId || agentOptions.value[0]?.id || '';
  }
  await loadData();
};

const loadData = async () => {
  if (!targetAgentId.value) return;
  try {
    isLoading.value = true;
    const [catalogData, stateData] = await Promise.all([
      chatStore.fetchMcpCatalogAction(),
      chatStore.fetchAgentMcpStateAction(targetAgentId.value)
    ]);
    catalog.value = catalogData;
    agentServers.value = stateData;
    for (const [name, meta] of Object.entries(catalogData)) {
      ensureDraft(name, meta.credentialFields || []);
    }
  } catch (err) {
    console.error('讀取 MCP 商店資料失敗:', err);
    ElMessage.error(`讀取失敗：${err?.response?.data?.error || err?.message || '未知錯誤'}`);
  } finally {
    isLoading.value = false;
  }
};

const handleToggleSelection = async (card, nextSelection) => {
  if (!targetAgentId.value) return;
  const kind = nextSelection === 'resident' || card.selection === 'resident' ? 'resident' : 'optional';
  try {
    togglingId.value = card.name + ':' + kind;
    await chatStore.setAgentMcpSelectionAction(targetAgentId.value, card.name, nextSelection);
    agentServers.value = {
      ...agentServers.value,
      [card.name]: { ...(agentServers.value[card.name] || {}), selection: nextSelection }
    };
    ElMessage.success(nextSelection ? `「${card.displayName}」設定成功，下次對話開始就會生效` : `已移除「${card.displayName}」`);
  } catch (err) {
    console.error('設定 MCP 失敗:', err);
    ElMessage.error(`設定失敗：${err?.response?.data?.error || err?.message || '未知錯誤'}`);
  } finally {
    togglingId.value = '';
  }
};

const handleSaveCredentials = async (card) => {
  if (!targetAgentId.value) return;
  try {
    savingCredId.value = card.name;
    const result = await chatStore.setAgentMcpCredentialsAction(targetAgentId.value, card.name, credentialDrafts[card.name]);
    agentServers.value = {
      ...agentServers.value,
      [card.name]: { ...(agentServers.value[card.name] || {}), credentialsConfigured: result?.entry?.credentialsConfigured || {} }
    };
    ElMessage.success(`「${card.displayName}」的憑證已儲存`);
  } catch (err) {
    console.error('儲存 MCP 憑證失敗:', err);
    ElMessage.error(`儲存失敗：${err?.response?.data?.error || err?.message || '未知錯誤'}`);
  } finally {
    savingCredId.value = '';
  }
};
</script>

<style scoped>
:deep(.mcp-market-dialog) {
  --market-blue-50: #f0f9ff;
  --market-blue-100: #e0f2fe;
  --market-blue-200: #bae6fd;
  --market-blue-400: #38bdf8;
  --market-blue-500: #0ea5e9;
  --market-blue-600: #0284c7;
  --market-blue-900: #0c4a6e;
  background:
    radial-gradient(circle at 15% 0%, rgba(56, 189, 248, 0.12), transparent 45%),
    radial-gradient(circle at 85% 100%, rgba(14, 165, 233, 0.10), transparent 45%),
    #f8fcff;
}

:deep(.el-dialog__header) {
  padding: 0 !important;
  margin: 0 !important;
  border-bottom: 1px solid var(--market-blue-100);
}

.market-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 22px 32px;
  background: linear-gradient(135deg, #eafaff 0%, #f5fbff 60%, #ffffff 100%);
}

.market-title { display: flex; align-items: center; gap: 14px; }
.market-icon { font-size: 34px; filter: drop-shadow(0 0 12px rgba(14, 165, 233, 0.35)); }
.market-title h1 { font-size: 20px; font-weight: 800; color: #0c4a6e; letter-spacing: 0.02em; margin: 0; }
.market-title p { font-size: 12px; color: #64748b; margin: 2px 0 0; }

.market-agent-picker {
  display: flex;
  align-items: center;
  gap: 10px;
  background: white;
  border: 1px solid var(--market-blue-200);
  padding: 8px 14px;
  border-radius: 14px;
  box-shadow: 0 4px 16px -8px rgba(14, 165, 233, 0.35);
}
.picker-label { font-size: 12px; font-weight: 600; color: #0369a1; white-space: nowrap; }
.agent-select { width: 200px; }

.market-body { display: flex; flex-direction: column; height: 100%; padding: 24px 32px 32px; overflow-y: auto; }

.empty-state {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 12px; padding: 100px 0; color: #94a3b8;
}
.empty-icon { font-size: 48px; }
.spin-icon { font-size: 32px; color: var(--market-blue-500); }

.results-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

.mcp-card {
  background: white;
  border: 1px solid var(--market-blue-100);
  border-radius: 16px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  transition: all 0.2s ease;
}
.mcp-card:hover {
  border-color: var(--market-blue-400);
  box-shadow: 0 12px 28px -14px rgba(14, 165, 233, 0.5);
  transform: translateY(-2px);
}

.mcp-card-top { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.mcp-name { font-size: 14px; font-weight: 700; color: #0c4a6e; }

.status-dot { font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 999px; white-space: nowrap; }
.dot-green { background: #dcfce7; color: #15803d; }
.dot-red { background: #fee2e2; color: #dc2626; }
.dot-neutral { background: #f1f5f9; color: #64748b; }

.mcp-desc { font-size: 12px; color: #475569; line-height: 1.5; min-height: 32px; }

.mcp-badges { display: flex; gap: 6px; }
.sel-badge { font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 999px; }
.sel-resident { background: #dbeafe; color: #1d4ed8; }
.sel-optional { background: #e0f2fe; color: #0369a1; }

.cred-form {
  display: flex;
  flex-direction: column;
  gap: 6px;
  background: var(--market-blue-50);
  border-radius: 10px;
  padding: 10px;
}
.cred-field { display: flex; flex-direction: column; gap: 2px; }
.cred-field label { font-size: 11px; font-weight: 600; color: #0369a1; }
.save-cred-btn { align-self: flex-end; }

.mcp-card-bottom { display: flex; gap: 8px; margin-top: 4px; }
</style>
