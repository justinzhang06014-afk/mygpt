<!-- src/components/SkillMarketplaceView.vue -->
<template>
  <el-dialog
    v-model="visible"
    fullscreen
    :show-close="true"
    class="skill-market-dialog"
    @open="handleOpen"
  >
    <template #header>
      <div class="market-header">
        <div class="market-title">
          <span class="market-icon">🛒</span>
          <div>
            <h1>Skill 商城</h1>
            <p>由 hermes 官方技能市集提供 · 即時搜尋 8 萬 8 千多個真實技能</p>
          </div>
        </div>

        <div class="market-agent-picker">
          <span class="picker-label">安裝到</span>
          <el-select v-model="targetAgentId" placeholder="選擇 Agent" class="agent-select" filterable>
            <el-option v-for="agent in agentOptions" :key="agent.id" :label="agent.name" :value="agent.id" />
          </el-select>
        </div>
      </div>
    </template>

    <div class="market-body">
      <div class="search-bar">
        <el-input
          v-model="searchQuery"
          size="large"
          placeholder="搜尋技能，例如：pdf、github、excel、影片剪輯…"
          class="search-input"
          clearable
          @keyup.enter="handleSearch"
        >
          <template #prefix>🔍</template>
        </el-input>
        <el-select v-model="sourceFilter" size="large" class="source-select">
          <el-option label="全部來源" value="all" />
          <el-option label="官方 Official" value="official" />
          <el-option label="skills.sh" value="skills-sh" />
          <el-option label="GitHub" value="github" />
          <el-option label="ClawHub" value="clawhub" />
        </el-select>
        <el-button type="primary" size="large" class="search-btn" :loading="isSearching" @click="handleSearch">
          搜尋
        </el-button>
      </div>

      <div class="results-scroll">
        <div v-if="!hasSearched" class="empty-state">
          <span class="empty-icon">🛰️</span>
          <p>輸入關鍵字，探索 hermes 官方技能市集</p>
        </div>

        <div v-else-if="isSearching" class="empty-state">
          <el-icon class="is-loading spin-icon"><Loading /></el-icon>
          <p>正在搜尋技能市集…</p>
        </div>

        <div v-else-if="results.length === 0" class="empty-state">
          <span class="empty-icon">🔭</span>
          <p>沒有找到符合「{{ lastQuery }}」的技能，換個關鍵字試試？</p>
        </div>

        <div v-else class="results-grid">
          <div v-for="skill in results" :key="skill.identifier" class="skill-card">
            <div class="skill-card-top">
              <span class="skill-name">{{ skill.name }}</span>
              <span class="trust-badge" :class="trustClass(skill.trust_level)">{{ skill.trust_level }}</span>
            </div>
            <p class="skill-desc">{{ skill.description }}</p>
            <div class="skill-card-bottom">
              <span class="source-tag">{{ skill.source }}</span>
              <el-button
                type="primary"
                size="small"
                class="install-btn"
                :loading="installingId === skill.identifier"
                :disabled="!targetAgentId"
                @click="handleInstall(skill)"
              >
                ⬇ 安裝
              </el-button>
            </div>
            <p class="skill-identifier">{{ skill.identifier }}</p>
          </div>
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, computed } from 'vue';
import { useChatStore } from '../stores/chat';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Loading } from '@element-plus/icons-vue';

const chatStore = useChatStore();
const visible = defineModel({ type: Boolean, default: false });

const searchQuery = ref('');
const sourceFilter = ref('all');
const results = ref([]);
const isSearching = ref(false);
const hasSearched = ref(false);
const lastQuery = ref('');
const installingId = ref('');
const targetAgentId = ref('');

const agentOptions = computed(() => (chatStore.agents || []).map(a => ({
  id: a.agent_id || a.AgentId,
  name: a.name || a.Name
})));

const handleOpen = () => {
  if (!targetAgentId.value) {
    targetAgentId.value = chatStore.currentAgentId || agentOptions.value[0]?.id || '';
  }
  if (!hasSearched.value) {
    searchQuery.value = '';
    results.value = [];
  }
};

const trustClass = (level) => {
  const l = (level || '').toLowerCase();
  if (l.includes('official')) return 'trust-official';
  if (l.includes('community')) return 'trust-community';
  return 'trust-other';
};

const handleSearch = async () => {
  if (!searchQuery.value.trim()) {
    ElMessage.warning('請輸入搜尋關鍵字！');
    return;
  }
  if (!targetAgentId.value) {
    ElMessage.warning('請先選擇要安裝技能的 Agent！');
    return;
  }
  try {
    isSearching.value = true;
    hasSearched.value = true;
    lastQuery.value = searchQuery.value.trim();
    const data = await chatStore.searchSkillsHubAction(targetAgentId.value, lastQuery.value, sourceFilter.value);
    results.value = data.results || [];
  } catch (err) {
    console.error('技能搜尋失敗:', err);
    ElMessage.error(`搜尋失敗：${err?.response?.data?.error || err?.message || '未知錯誤'}`);
  } finally {
    isSearching.value = false;
  }
};

const handleInstall = async (skill, force = false) => {
  if (!targetAgentId.value) return;
  try {
    installingId.value = skill.identifier;
    const result = await chatStore.installSkillFromHubAction(targetAgentId.value, skill.identifier, force);
    // 🛡️【實測發現】就算被 hermes 自己的資安掃描擋下來，這支端點還是回 HTTP 200，
    // 一定要看後端回傳的 outcome 才知道到底是「真的裝好了」還是「被擋下來了」，
    // 不能只看 API 呼叫有沒有丟例外就顯示安裝成功。
    if (result?.outcome === 'blocked') {
      installingId.value = '';
      try {
        await ElMessageBox.confirm(
          result.security_report || '（hermes 未提供詳細說明）',
          `⚠️ hermes 資安掃描擋下「${skill.name}」`,
          {
            confirmButtonText: '我了解風險，仍要安裝',
            cancelButtonText: '取消',
            type: 'warning',
            customStyle: { whiteSpace: 'pre-wrap' }
          }
        );
        await handleInstall(skill, true);
      } catch {
        // 使用者取消，不用額外處理
      }
      return;
    }
    if (result?.outcome === 'installed') {
      ElMessage.success(`🎉 技能「${skill.name}」已成功安裝到 Agent！`);
    } else {
      ElMessage.warning(`技能「${skill.name}」安裝結果不明，請稍後重新確認`);
    }
  } catch (err) {
    console.error('安裝技能失敗:', err);
    ElMessage.error(`安裝失敗：${err?.response?.data?.error || err?.message || '未知錯誤'}`);
  } finally {
    installingId.value = '';
  }
};
</script>

<style scoped>
:deep(.skill-market-dialog) {
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

.market-title {
  display: flex;
  align-items: center;
  gap: 14px;
}
.market-icon {
  font-size: 34px;
  filter: drop-shadow(0 0 12px rgba(14, 165, 233, 0.35));
}
.market-title h1 {
  font-size: 20px;
  font-weight: 800;
  color: #0c4a6e;
  letter-spacing: 0.02em;
  margin: 0;
}
.market-title p {
  font-size: 12px;
  color: #64748b;
  margin: 2px 0 0;
}

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
.picker-label {
  font-size: 12px;
  font-weight: 600;
  color: #0369a1;
  white-space: nowrap;
}
.agent-select {
  width: 200px;
}

.market-body {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 24px 32px 0;
}

.search-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}
.search-input {
  flex: 1;
}
.source-select {
  width: 160px;
}
.search-btn {
  background: linear-gradient(135deg, var(--market-blue-500), var(--market-blue-600));
  border: none;
  padding: 0 28px;
  box-shadow: 0 8px 20px -8px rgba(2, 132, 199, 0.55);
}

.results-scroll {
  flex: 1;
  overflow-y: auto;
  padding-bottom: 32px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 100px 0;
  color: #94a3b8;
}
.empty-icon { font-size: 48px; }
.spin-icon { font-size: 32px; color: var(--market-blue-500); }

.results-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.skill-card {
  background: white;
  border: 1px solid var(--market-blue-100);
  border-radius: 16px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  transition: all 0.2s ease;
  position: relative;
  overflow: hidden;
}
.skill-card::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(56, 189, 248, 0.06), transparent 60%);
  pointer-events: none;
}
.skill-card:hover {
  border-color: var(--market-blue-400);
  box-shadow: 0 12px 28px -14px rgba(14, 165, 233, 0.5);
  transform: translateY(-2px);
}

.skill-card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.skill-name {
  font-size: 14px;
  font-weight: 700;
  color: #0c4a6e;
}

.trust-badge {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 999px;
  white-space: nowrap;
  text-transform: uppercase;
}
.trust-official { background: #dbeafe; color: #1d4ed8; }
.trust-community { background: #e0f2fe; color: #0369a1; }
.trust-other { background: #f1f5f9; color: #64748b; }

.skill-desc {
  font-size: 12px;
  color: #475569;
  line-height: 1.5;
  min-height: 36px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.skill-card-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 4px;
}
.source-tag {
  font-size: 10px;
  color: #0284c7;
  background: var(--market-blue-50);
  padding: 3px 8px;
  border-radius: 8px;
  font-weight: 600;
}
.install-btn {
  background: linear-gradient(135deg, var(--market-blue-500), var(--market-blue-600));
  border: none;
}

.skill-identifier {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 10px;
  color: #94a3b8;
  margin: 0;
  word-break: break-all;
}
</style>
