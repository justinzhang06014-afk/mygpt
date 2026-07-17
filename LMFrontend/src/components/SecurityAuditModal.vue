<!-- src/components/SecurityAuditModal.vue -->
<template>
  <el-dialog
    v-model="visible"
    fullscreen
    class="security-audit-dialog"
    @open="runAudit"
  >
    <template #header>
      <div class="audit-header">
        <span class="audit-icon">🛡️</span>
        <div>
          <h1>供應鏈安全掃描</h1>
          <p>即時執行 <code>hermes security audit</code>，向 OSV.dev 查詢已安裝套件／技能／MCP 伺服器的已知漏洞</p>
        </div>
      </div>
    </template>

    <div class="audit-body">
      <div v-if="isLoading" class="state-block">
        <el-icon class="is-loading spin-icon"><Loading /></el-icon>
        <p>正在向 OSV.dev 查詢，最長可能需要 60 秒…</p>
      </div>

      <div v-else-if="errorMsg" class="state-block error-block">
        <span class="state-icon">❌</span>
        <p>{{ errorMsg }}</p>
      </div>

      <template v-else-if="report">
        <div v-if="report.raw" class="raw-report">{{ report.raw }}</div>

        <template v-else>
          <div class="stat-row">
            <div class="stat-card">
              <span class="stat-label">已掃描元件</span>
              <span class="stat-value">{{ report.total_components_scanned ?? '—' }}</span>
            </div>
            <div class="stat-card" :class="report.finding_count > 0 ? 'stat-danger' : 'stat-safe'">
              <span class="stat-label">發現漏洞</span>
              <span class="stat-value">{{ report.finding_count ?? 0 }}</span>
            </div>
          </div>

          <div v-if="!report.findings || report.findings.length === 0" class="state-block safe-block">
            <span class="state-icon">✅</span>
            <p>未發現已知漏洞</p>
          </div>

          <div v-else class="findings-grid">
            <div v-for="(finding, idx) in report.findings" :key="idx" class="finding-card">
              <div class="finding-top">
                <span class="finding-pkg">{{ finding.package }}@{{ finding.version }}</span>
                <span class="severity-badge" :class="severityClass(finding.severity)">{{ finding.severity }}</span>
              </div>
              <p class="finding-summary">{{ finding.summary }}</p>
              <p class="finding-meta">
                {{ finding.vuln_id }} · 來源: {{ finding.source }}
                <span v-if="finding.fixed_versions?.length"> · 修復版本: {{ finding.fixed_versions.join(', ') }}</span>
              </p>
            </div>
          </div>
        </template>
      </template>
    </div>

    <template #footer>
      <div class="audit-footer">
        <el-button @click="visible = false">關閉</el-button>
        <el-button type="primary" :loading="isLoading" @click="runAudit">🔄 重新掃描</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref } from 'vue';
import { useChatStore } from '../stores/chat';
import { Loading } from '@element-plus/icons-vue';

const chatStore = useChatStore();
const visible = defineModel({ type: Boolean, default: false });

const isLoading = ref(false);
const errorMsg = ref('');
const report = ref(null);

const severityClass = (severity) => {
  const s = (severity || '').toUpperCase();
  if (s === 'CRITICAL' || s === 'HIGH') return 'sev-high';
  if (s === 'MODERATE') return 'sev-moderate';
  return 'sev-low';
};

const runAudit = async () => {
  if (!chatStore.currentAgentId) {
    errorMsg.value = '目前不在任何 Agent 的辦公室中，無法掃描。';
    return;
  }
  isLoading.value = true;
  errorMsg.value = '';
  report.value = null;
  try {
    const data = await chatStore.runSecurityAuditAction(chatStore.currentAgentId);
    report.value = data.report;
  } catch (err) {
    console.error('安全掃描失敗:', err);
    errorMsg.value = err?.response?.data?.error || err?.message || '未知錯誤';
  } finally {
    isLoading.value = false;
  }
};
</script>

<style scoped>
:deep(.security-audit-dialog) {
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

.audit-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 22px 32px;
  background: linear-gradient(135deg, #eafaff 0%, #f5fbff 60%, #ffffff 100%);
}
.audit-icon {
  font-size: 34px;
  filter: drop-shadow(0 0 12px rgba(14, 165, 233, 0.35));
}
.audit-header h1 {
  font-size: 20px;
  font-weight: 800;
  color: #0c4a6e;
  margin: 0;
}
.audit-header p {
  font-size: 12px;
  color: #64748b;
  margin: 2px 0 0;
}
.audit-header code {
  background: #e0f2fe;
  color: #0369a1;
  padding: 1px 6px;
  border-radius: 6px;
}

.audit-body {
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

.raw-report {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  white-space: pre-wrap;
  background: white;
  border: 1px solid #e0f2fe;
  border-radius: 16px;
  padding: 20px;
}

.stat-row {
  display: flex;
  gap: 16px;
  margin-bottom: 24px;
}
.stat-card {
  flex: 1;
  background: white;
  border: 1px solid #e0f2fe;
  border-radius: 16px;
  padding: 18px 22px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.stat-label { font-size: 12px; color: #64748b; font-weight: 600; }
.stat-value { font-size: 28px; font-weight: 800; color: #0c4a6e; }
.stat-danger .stat-value { color: #dc2626; }
.stat-safe .stat-value { color: #059669; }

.findings-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.finding-card {
  background: white;
  border: 1px solid #e0f2fe;
  border-radius: 14px;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.finding-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.finding-pkg { font-weight: 700; font-size: 14px; color: #0c4a6e; }
.severity-badge {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 10px;
  border-radius: 999px;
  text-transform: uppercase;
}
.sev-high { background: #fee2e2; color: #dc2626; }
.sev-moderate { background: #fef3c7; color: #b45309; }
.sev-low { background: #f1f5f9; color: #64748b; }
.finding-summary { font-size: 12px; color: #475569; }
.finding-meta { font-size: 11px; color: #94a3b8; }

.audit-footer {
  display: flex;
  justify-content: center;
  gap: 12px;
  padding: 16px;
}
</style>
