<!-- src/components/MessageBubble.vue -->
<!-- src/components/MessageBubble.vue -->
<template>
  <div :class="['message-row flex w-full gap-4 group', msg.role === 'user' ? 'flex-row-reverse' : 'flex-row']">
    <!-- 1. 頭像區域：AI (Hermes) 採用配合你色系的深科技藍底與青色標籤 -->
    <div :class="['avatar-box w-9 h-9 rounded-xl flex items-center justify-center text-base shadow-sm shrink-0 select-none transition-all duration-300', msg.role === 'user' ? 'bg-[#bbdefb]' : 'bg-[#1e3a8a] text-[#e1eef8] border border-[#d0e1f0] font-mono text-[11px] font-bold tracking-tighter']">
      {{ msg.role === 'user' ? '👤' : 'HMS' }}
    </div>
    
    <div :class="['flex flex-col max-w-[85%]', msg.role === 'user' ? 'items-end' : 'items-start']">
      <!-- 編輯狀態卡片（保留你原本的元件結構） -->
      <div v-if="msg.role === 'user' && isEditing" class="edit-card w-72 sm:w-96 bg-white p-3 rounded-xl shadow-lg border border-[#e5e7eb] flex flex-col gap-3">
        <el-input v-model="localText" type="textarea" :rows="2" resize="none" />
        <div class="flex justify-between items-center">
          <el-checkbox v-model="localSearch" size="small">🌐 聯網搜尋</el-checkbox>
          <div class="flex gap-2">
            <el-button size="small" @click="emit('cancel-edit')">取消</el-button>
            <el-button size="small" type="primary" :loading="isLoading" @click="emit('submit-edit', { id: msg.id, text: localText, search: localSearch })">儲存送出</el-button>
          </div>
        </div>
      </div>

      <!-- 正常訊息顯示 -->
      <div v-else class="flex flex-col gap-2 w-full">
        <!-- Google 引用資料卡片流（保留並微調外觀使其融入 Cyber Blue） -->
        <div v-if="msg.role === 'assistant' && msg.searchSources?.length > 0" class="w-full flex flex-col gap-1.5 mb-1">
          <div class="text-xs text-[#1e3a8a] flex items-center gap-1 font-bold select-none tracking-wide">🔍 已參考 Google 即時資料：</div>
          <div class="flex gap-2 overflow-x-auto pb-1 max-w-full scrollbar-thin">
            <a v-for="(src, idx) in msg.searchSources" :key="idx" :href="src.link" target="_blank" class="flex-shrink-0 w-44 bg-[#f0f5fa] hover:bg-[#e1eef8] border border-[#d0e1f0] p-2 rounded-xl text-left shadow-2xs transition-all duration-200 group/card">
              <h4 class="text-xs font-semibold text-[#1e3a8a] truncate">{{ src.title }}</h4>
              <p class="text-[10px] text-[#60a5fa] truncate mt-0.5">{{ src.snippet }}</p>
            </a>
          </div>
        </div>

        <!-- 對話氣泡本體：整合你指定的 Cyber Blue 淡藍基底與 Hermes 終端機格式 -->
        <div :class="['bubble px-4 py-3 rounded-2xl shadow-sm border text-[15px] leading-relaxed transition-all duration-200 w-full', msg.role === 'user' ? 'bg-[#e3f2fd] border-[#c4e1f6] text-[#0d47a1] rounded-tr-none' : 'bg-[#f0f5fa] border-[#d0e1f0] text-[#1e3a8a] rounded-tl-none']">
          
          <!-- 使用者對話文本 -->
          <p v-if="msg.role === 'user'" class="m-0 whitespace-pre-wrap">{{ msg.content }}</p>
          
          <!-- AI (Hermes) 科技感混合監控面板 -->
          <div v-else class="hermes-interactive-panel flex flex-col gap-3">

            <!-- ⚡ A. 【Hermes 正在思考】動態載入區 -->
            <div v-if="isLoading" class="hermes-status-banner flex items-center justify-between bg-[#e1eef8] border border-[#cbdff2] rounded-xl px-4 py-2.5">
              <div class="flex items-center gap-3">
                <div class="hermes-glow-spinner"></div>
                <div class="flex flex-col">
                  <span class="text-xs font-mono text-[#1e88e5] font-bold tracking-wider animate-pulse">HERMES KERNEL PROCESSING</span>
                  <span class="text-[10px] font-mono text-[#60a5fa]">Memory Check & Prompt Injecting...</span>
                </div>
              </div>
              <div class="text-[10px] font-mono font-bold text-[#0d47a1] bg-[#d0e6f7] border border-[#b3d7f2] px-2 py-0.5 rounded-md">
                CORE_ACTIVE
              </div>
            </div>

            <!-- 🆕 0716：B.【思考過程】hermes acp 的 AgentThoughtChunk 事件，真實資料，可收合 -->
            <div v-if="msg.thoughts" class="thought-panel border border-[#e0e7ff] rounded-xl overflow-hidden bg-[#f8f7ff]">
              <button type="button" class="thought-header w-full flex items-center justify-between px-3 py-2 bg-[#f0eeff] text-left" @click="thoughtExpanded = !thoughtExpanded">
                <span class="text-xs font-bold text-[#5b21b6] flex items-center gap-1.5">💭 思考過程</span>
                <span class="text-[10px] text-[#7c3aed]">{{ thoughtExpanded ? '收合 ▲' : '展開 ▼' }}</span>
              </button>
              <div v-if="thoughtExpanded" class="px-3 py-2 text-xs text-[#5b21b6] whitespace-pre-wrap leading-relaxed">{{ msg.thoughts }}</div>
            </div>

            <!-- 🆕 0716：C.【工具呼叫卡片】hermes acp 的 ToolCallStart/ToolCallProgress 事件，
                 每個工具呼叫獨立一張卡片，狀態(pending/completed/failed)直接來自 hermes，不用猜 -->
            <div v-if="msg.toolCalls?.length" class="flex flex-col gap-2">
              <div v-for="tc in msg.toolCalls" :key="tc.tool_call_id" class="tool-call-card border rounded-xl p-3" :class="toolCardClass(tc.status)">
                <div class="flex items-center justify-between gap-2">
                  <span class="text-xs font-bold flex items-center gap-1.5">
                    <span>{{ toolStatusIcon(tc.status) }}</span>
                    <span>{{ tc.title || tc.kind || '工具呼叫' }}</span>
                  </span>
                  <span class="text-[10px] font-mono opacity-70">{{ tc.status || 'pending' }}</span>
                </div>
              </div>
            </div>

            <!-- 🆕 0716：D.【計畫/Todo 更新】hermes acp 的 AgentPlanUpdate 事件 -->
            <div v-if="msg.plan?.length" class="plan-panel border border-[#dbeafe] rounded-xl p-3 bg-[#f5f9ff]">
              <div class="text-xs font-bold text-[#1d4ed8] mb-1.5">📋 執行計畫</div>
              <ul class="flex flex-col gap-1 m-0 pl-0" style="list-style:none">
                <li v-for="(item, idx) in msg.plan" :key="idx" class="text-xs text-[#1e3a8a] flex items-center gap-1.5">
                  <span>{{ item.status === 'completed' ? '✅' : item.status === 'in_progress' ? '🔄' : '⬜' }}</span>
                  <span>{{ item.content }}</span>
                </li>
              </ul>
            </div>

            <!-- 📝 E. 【標準 Markdown 回覆區】 -->
            <div v-if="cleanContent" class="markdown-body custom-cyber-markdown" v-html="renderedContent" ref="contentRef"></div>

            <!-- 🆕 0716：F.【用量統計】hermes acp 的 UsageUpdate 事件，小小的參考資訊，不搶眼 -->
            <div v-if="msg.usage" class="text-[10px] text-[#94a3b8] font-mono">
              context: {{ msg.usage.used }} / {{ msg.usage.size }} tokens
            </div>

            <!-- 🧭 D. 【Skill 推薦卡片】後端偵測到對話內容可能需要某個尚未安裝的技能時顯示 -->
            <div v-if="msg.skillSuggestion && skillCardVisible" class="skill-suggestion-card flex flex-col gap-2 bg-[#eef6ff] border border-[#bcdcfb] rounded-xl p-3">
              <div class="flex items-center gap-2 text-[13px] text-[#0d47a1] font-semibold">
                <span>🧭</span>
                <span>偵測到你可能需要「{{ msg.skillSuggestion.name }}」這個技能</span>
              </div>
              <div v-if="msg.skillSuggestion.description" class="text-[12px] text-[#3b6ea8]">
                {{ msg.skillSuggestion.description }}
              </div>

              <!-- 🛡️ hermes 資安掃描擋下來時，把它實際講的風險內容原封不動秀出來 -->
              <div v-if="skillInstallStatus === 'blocked'" class="bg-[#fff3e0] border border-[#ffcc80] rounded-lg p-2.5 flex flex-col gap-1.5">
                <div class="text-[12px] text-[#e65100] font-bold">⚠️ hermes 資安掃描回報風險，已阻擋安裝：</div>
                <pre class="text-[11px] text-[#5d4037] whitespace-pre-wrap font-mono bg-white/60 rounded p-2 m-0 max-h-40 overflow-y-auto">{{ skillSecurityReport }}</pre>
              </div>

              <div class="flex gap-2 items-center flex-wrap">
                <el-button
                  v-if="skillInstallStatus !== 'blocked'"
                  size="small"
                  type="primary"
                  :loading="skillInstallStatus === 'installing'"
                  :disabled="skillInstallStatus === 'done'"
                  @click="handleInstallSkillClick(false)"
                >
                  {{ skillInstallStatus === 'done' ? '✅ 已安裝' : '安裝這個技能' }}
                </el-button>

                <!-- 使用者看過風險說明後，仍然要裝的話才給這個選項 -->
                <el-button
                  v-else
                  size="small"
                  type="danger"
                  plain
                  :loading="skillInstallStatus === 'installing'"
                  @click="handleInstallSkillClick(true)"
                >
                  我了解風險，仍要安裝
                </el-button>

                <el-button size="small" text @click="skillCardVisible = false">略過</el-button>
                <span v-if="skillInstallStatus === 'error'" class="text-[12px] text-[#c62828]">{{ skillInstallErrorReason }}</span>
              </div>
            </div>

          </div>
        </div>
      </div>
      
      <!-- 懸浮操作鈕（保留你原本的結構） -->
      <div v-if="msg.role === 'user' && msg.id && !isEditing" class="action-group flex gap-3 mt-1.5 px-1 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
        <button class="text-xs text-[#9ca3af] hover:text-[#42a5f5]" @click="emit('start-edit', msg)">編輯</button>
        <span class="text-[10px] text-[#e5e7eb] self-center">|</span>
        <button class="text-xs text-[#9ca3af] hover:text-[#ef5350]" @click="emit('retract', msg.id)">收回</button>
      </div>
    </div>
  </div>
</template>


<script setup>
import { ref, watch, computed, onMounted, onUpdated, nextTick } from 'vue';
import { Marked } from 'marked';
import Prism from 'prismjs';
import 'prismjs/themes/prism.css';
import { useChatStore } from '../stores/chat';

const props = defineProps({ msg: Object, isEditing: Boolean, isLoading: Boolean });
const emit = defineEmits(['start-edit', 'cancel-edit', 'submit-edit', 'retract']);

const chatStore = useChatStore();
const localText = ref(props.msg.content);
const localSearch = ref(false);
const contentRef = ref(null);

// =========================================================================
// 🧭 Skill 推薦卡片：狀態完全自己管理，不用跟父層 ChatRoom.vue 來回傳遞。
// 點擊「安裝」直接呼叫既有的 installSkillFromHubAction —— 跟商城搜尋頁面
// 點安裝時走的是同一支後端端點，這裡只是多了一個「什麼時候該建議」的判斷。
// =========================================================================
const skillCardVisible = ref(true);
const skillInstallStatus = ref('idle'); // idle | installing | done | blocked | error
const skillInstallErrorReason = ref('');
const skillSecurityReport = ref('');

const handleInstallSkillClick = async (force = false) => {
  if (!props.msg.skillSuggestion || !chatStore.currentAgentId) return;
  skillInstallStatus.value = 'installing';
  skillInstallErrorReason.value = '';
  try {
    const result = await chatStore.installSkillFromHubAction(chatStore.currentAgentId, props.msg.skillSuggestion.identifier, force);
    // 🛡️【實測發現】hermes CLI 就算被自己的資安掃描擋下來，install-from-hub 這支端點
    // 還是會回 HTTP 200 + status: success（指令本身「執行成功」不代表「真的裝進去了」）。
    // 後端已經改成回傳結構化的 outcome / security_report，不用自己再去猜 stdout 字串。
    if (result?.outcome === 'installed') {
      skillInstallStatus.value = 'done';
    } else if (result?.outcome === 'blocked') {
      skillInstallStatus.value = 'blocked';
      skillSecurityReport.value = result.security_report || '（hermes 未提供詳細說明）';
    } else {
      skillInstallStatus.value = 'error';
      skillInstallErrorReason.value = '安裝未完成，請稍後再試';
    }
  } catch (err) {
    console.error('❌ [Skill 推薦] 安裝失敗:', err);
    skillInstallStatus.value = 'error';
    skillInstallErrorReason.value = '安裝失敗，稍後再試一次';
  }
};

const marked = new Marked();

// =========================================================================
// 🗑️ 0716 移除：舊版靠關鍵字猜「這是不是後端日誌」、用固定分隔符 '┊' 切文字，
// 甚至寫死一組 yahoo.com 假指令範本去冒充真實執行內容的整套 parser。
// 改用 hermes acp 結構化事件（見 chat.js 的 __ACP_THOUGHT__/__ACP_TOOL__/
// __ACP_PLAN__ 處理），msg.content 現在就是純淨的最終回覆文字，不需要再猜、
// 更不需要在猜不到的時候顯示假資料。
// =========================================================================

const cleanContent = computed(() => props.msg.content || '');

const renderedContent = computed(() => marked.parse(cleanContent.value || ''));

// 🆕 0716：工具呼叫卡片的狀態顏色/圖示，直接對應 hermes acp 回報的真實 status 值
const thoughtExpanded = ref(false);

const toolCardClass = (status) => {
  if (status === 'completed') return 'bg-[#f0fdf4] border-[#bbf7d0] text-[#15803d]';
  if (status === 'failed') return 'bg-[#fef2f2] border-[#fecaca] text-[#dc2626]';
  return 'bg-[#eff6ff] border-[#bfdbfe] text-[#1d4ed8]'; // pending/in_progress 等其餘狀態
};

const toolStatusIcon = (status) => {
  if (status === 'completed') return '✅';
  if (status === 'failed') return '❌';
  return '⚙️';
};

// =========================================================================
// 📥 CODEBLOCK EXTENSION TOOLS (原有控制列與檔案生成功能)
// =========================================================================
const getFileExtension = (langClass) => {
  if (!langClass) return 'txt';
  const lang = langClass.replace('language-', '').toLowerCase();
  const extMap = { python: 'py', javascript: 'js', typescript: 'ts', html: 'html', css: 'css', json: 'json', markdown: 'md', csharp: 'cs' };
  return extMap[lang] || lang;
};

const injectCodeFeatures = async () => {
  await nextTick();
  if (!contentRef.value) return;

  Prism.highlightAllUnder(contentRef.value);

  const preBlocks = contentRef.value.querySelectorAll('pre');
  preBlocks.forEach((pre) => {
    if (pre.querySelector('.code-action-bar')) return;

    pre.style.position = 'relative';
    pre.style.paddingTop = '40px'; 

    const codeEl = pre.querySelector('code');
    const langClass = codeEl ? Array.from(codeEl.classList).find(c => c.startsWith('language-')) : '';
    const langName = langClass ? langClass.replace('language-', '').toUpperCase() : 'CODE';

    const actionBar = document.createElement('div');
    actionBar.className = 'code-action-bar';

    const langTag = document.createElement('span');
    langTag.className = 'code-lang-tag';
    langTag.innerText = langName;
    actionBar.appendChild(langTag);

    const btnGroup = document.createElement('div');
    btnGroup.className = 'code-btn-group';

    const copyBtn = document.createElement('button');
    copyBtn.className = 'code-action-btn';
    copyBtn.innerText = '📋 複製';
    copyBtn.addEventListener('click', async () => {
      const codeText = codeEl?.innerText || '';
      try {
        await navigator.clipboard.writeText(codeText);
        copyBtn.innerText = '✅ 已複製';
        setTimeout(() => { copyBtn.innerText = '📋 複製'; }, 2000);
      } catch (err) {
        copyBtn.innerText = '❌ 失敗';
      }
    });
    btnGroup.appendChild(copyBtn);

    const downloadBtn = document.createElement('button');
    downloadBtn.className = 'code-action-btn download-btn';
    downloadBtn.innerText = '📥 下載檔案';
    downloadBtn.addEventListener('click', () => {
      const codeText = codeEl?.innerText || '';
      const ext = getFileExtension(langClass);
      
      const blob = new Blob([codeText], { type: 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `generated_code_${Date.now()}.${ext}`;
      document.body.appendChild(a);
      a.click();
      
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    });
    btnGroup.appendChild(downloadBtn);

    actionBar.appendChild(btnGroup);
    pre.insertBefore(actionBar, pre.firstChild);
  });
};

onMounted(injectCodeFeatures);
onUpdated(injectCodeFeatures);
watch(() => props.msg.content, (newVal) => localText.value = newVal);
</script>


<style scoped>
/* =========================================================================
   🎨 高質感 Cyber Blue 淡藍色程式碼區塊與系統 HUD 樣式表
   ========================================================================= */

/* 🌀 核心科技感旋轉圖示：流暢的微光漸變動畫（Hermes正在思考） */
.hermes-glow-spinner {
  width: 22px;
  height: 22px;
  border: 2.5px solid rgba(96, 165, 250, 0.2); /* 柔和淡藍底圈 */
  border-top-color: #1e88e5; /* 科技藍主動條 */
  border-radius: 50%;
  animation: hermes-spin 0.85s cubic-bezier(0.4, 0, 0.2, 1) infinite;
  box-shadow: 0 0 8px rgba(30, 136, 229, 0.25);
}

@keyframes hermes-spin {
  to { transform: rotate(360deg); }
}

/* 💻 終端機 HUD 面板基底滾動條微調（保持清爽不突兀） */
.scrollbar-thin::-webkit-scrollbar {
  height: 6px;
  width: 6px;
}
.scrollbar-thin::-webkit-scrollbar-track {
  background: #fafbfc;
  border-bottom-right-radius: 11px;
}
.scrollbar-thin::-webkit-scrollbar-thumb {
  background: #cbdff2;
  border-radius: 9999px;
}
.scrollbar-thin::-webkit-scrollbar-thumb:hover {
  background: #90caf9;
}

/* 🎯 Markdown 渲染主體：導入你最愛的低飽和淡藍灰底色系 */
.custom-cyber-markdown {
  line-height: 1.6;
}

/* 大塊程式碼區塊基底 */
.custom-cyber-markdown :deep(pre) {
  position: relative;
  background-color: #f0f5fa !important; 
  border: 1px solid #d0e1f0 !important;
  padding: 1rem;
  padding-top: 42px; /* 預留給控制列的舒適空間 */
  border-radius: 12px;
  overflow-x: auto;
  margin: 0.8em 0;
  box-shadow: inset 0 1px 2px rgba(30, 58, 138, 0.03);
}

/* 程式碼字體與顏色微調 */
.custom-cyber-markdown :deep(code) {
  font-family: 'Fira Code', Consolas, Monaco, monospace;
  font-size: 14px;
  color: #1e3a8a !important; /* 深科技藍字體 */
}

/* 🎯 頂部控制列：高質感亮色淡藍橫條 */
:deep(.code-action-bar) {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 34px;
  background-color: #e1eef8;
  border-bottom: 1px solid #d0e1f0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 12px;
  border-top-left-radius: 11px;
  border-top-right-radius: 11px;
  user-select: none;
}

/* 語言標籤樣式 */
:deep(.code-lang-tag) {
  font-size: 11px;
  font-weight: 700;
  color: #60a5fa;
  letter-spacing: 0.5px;
}

/* 按鈕群組 */
:deep(.code-btn-group) {
  display: flex;
  gap: 8px;
}

/* 極簡科技感操作按鈕 */
:deep(.code-action-btn) {
  background: transparent;
  border: none;
  color: #1e88e5;
  font-size: 12px;
  font-weight: 500;
  padding: 2px 6px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s ease-in-out;
}

:deep(.code-action-btn:hover) {
  background-color: #d0e6f7;
  color: #0d47a1;
}

/* 下載按鈕特別強調色 */
:deep(.download-btn) {
  color: #2e7d32; /* 沉穩優雅的工程綠 */
}
:deep(.download-btn:hover) {
  background-color: #c8e6c9;
  color: #1b5e20;
}

/* 🎯 句子內夾帶的單行小程式碼（例如 `app.py`） */
.custom-cyber-markdown :deep(:not(pre) > code) {
  background-color: #e3f2fd;
  color: #0d47a1;
  padding: 0.2em 0.4em;
  border-radius: 6px;
  font-size: 13px;
  border: 1px solid #bbdefb;
}

/* 清除外邊距干擾 */
.custom-cyber-markdown :deep(p:first-child) { margin-top: 0; }
.custom-cyber-markdown :deep(p:last-child) { margin-bottom: 0; }
.custom-cyber-markdown :deep(p) { margin-bottom: 0.75rem; color: #1e3a8a; }

/* =========================================================================
   🖥️ Hermes 專屬 HUD 系統日誌面板額外優化
   ========================================================================= */
.hermes-terminal-hud {
  box-shadow: 0 4px 12px rgba(30, 58, 138, 0.05);
}

.hermes-terminal-hud :deep(pre) {
  margin: 0.4em 0 !important;
  padding: 0.75rem !important;
  border-radius: 8px !important;
}

.hermes-status-banner {
  box-shadow: 0 2px 6px rgba(30, 136, 229, 0.04);
}
</style>
