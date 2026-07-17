<!-- src/components/MessageBubble.vue -->
<template>
  <div :class="['message-row flex w-full gap-4 group', msg.role === 'user' ? 'flex-row-reverse' : 'flex-row']">
    <div :class="['avatar-box w-9 h-9 rounded-xl flex items-center justify-center text-base shadow-sm shrink-0 select-none', msg.role === 'user' ? 'bg-[#bbdefb]' : 'bg-white border border-[#e5e7eb]']">
      {{ msg.role === 'user' ? '👤' : '🤖' }}
    </div>
    
    <div :class="['flex flex-col max-w-full', msg.role === 'user' ? 'items-end' : 'items-start']">
      <!-- 編輯狀態卡片 -->
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
        <!-- Google 引用資料卡片流 -->
        <div v-if="msg.role === 'assistant' && msg.searchSources?.length > 0" class="w-full flex flex-col gap-1.5 mb-1">
          <div class="text-xs text-[#9ca3af] flex items-center gap-1 font-medium select-none">🔍 已參考 Google 即時資料：</div>
          <div class="flex gap-2 overflow-x-auto pb-1 max-w-full scrollbar-thin">
            <a v-for="(src, idx) in msg.searchSources" :key="idx" :href="src.link" target="_blank" class="flex-shrink-0 w-44 bg-white hover:bg-[#f4faff] border border-[#e5e7eb] hover:border-[#90caf9] p-2 rounded-xl text-left shadow-2xs transition-all duration-200 group/card">
              <h4 class="text-xs font-semibold text-[#374151] truncate group-hover/card:text-[#1e88e5]">{{ src.title }}</h4>
              <p class="text-[10px] text-[#9ca3af] truncate mt-0.5">{{ src.snippet }}</p>
            </a>
          </div>
        </div>

        <!-- 对话气泡本体 -->
        <div :class="['bubble px-4 py-3 rounded-2xl shadow-sm border text-[15px] leading-relaxed transition-all duration-200', msg.role === 'user' ? 'bg-[#e3f2fd] border-[#c4e1f6] text-[#0d47a1] rounded-tr-none' : 'bg-white border-[#e5e7eb] text-[#1f2937] rounded-tl-none']">
          <p v-if="msg.role === 'user'" class="m-0 whitespace-pre-wrap">{{ msg.content }}</p>
          <!-- AI 回答：高質感淡藍色調 Markdown 渲染區 -->
          <div v-else class="markdown-body" v-html="renderedContent" ref="contentRef"></div>
        </div>
      </div>
      
      <!-- 懸浮極簡操作鈕 -->
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
// 💡 改用優雅亮色系的 prism 主題，方便我們覆蓋微調成高質感淡藍色
import 'prismjs/themes/prism.css';

const props = defineProps({ msg: Object, isEditing: Boolean, isLoading: Boolean });
const emit = defineEmits(['start-edit', 'cancel-edit', 'submit-edit', 'retract']);

const localText = ref(props.msg.content);
const localSearch = ref(false);
const contentRef = ref(null);

const marked = new Marked();

const renderedContent = computed(() => {
  if (!props.msg.content) return '';
  return marked.parse(props.msg.content);
});

// 💡 偵測程式碼種類並回傳副檔名的防禦小工具
const getFileExtension = (langClass) => {
  if (!langClass) return 'txt';
  const lang = langClass.replace('language-', '').toLowerCase();
  const extMap = { python: 'py', javascript: 'js', typescript: 'ts', html: 'html', css: 'css', json: 'json', markdown: 'md', csharp: 'cs' };
  return extMap[lang] || lang;
};

// 💡 注入高顏值頂部控制列（包含：語言標籤、複製按鈕、直產下載按鈕）
const injectCodeFeatures = async () => {
  await nextTick();
  if (!contentRef.value) return;

  Prism.highlightAllUnder(contentRef.value);

  const preBlocks = contentRef.value.querySelectorAll('pre');
  preBlocks.forEach((pre) => {
    // 避免重複渲染
    if (pre.querySelector('.code-action-bar')) return;

    pre.style.position = 'relative';
    pre.style.paddingTop = '40px'; // 留空間給頂部淡藍色控制列

    // 取得程式碼語言
    const codeEl = pre.querySelector('code');
    const langClass = codeEl ? Array.from(codeEl.classList).find(c => c.startsWith('language-')) : '';
    const langName = langClass ? langClass.replace('language-', '').toUpperCase() : 'CODE';

    // 建立頂部控制列
    const actionBar = document.createElement('div');
    actionBar.className = 'code-action-bar';

    // 1. 語言標籤
    const langTag = document.createElement('span');
    langTag.className = 'code-lang-tag';
    langTag.innerText = langName;
    actionBar.appendChild(langTag);

    // 右側按鈕群組
    const btnGroup = document.createElement('div');
    btnGroup.className = 'code-btn-group';

    // 2. 📋 複製按鈕
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

    // 3. 📥 直產下載檔案按鈕（直接打包程式碼讓使用者下載）
    const downloadBtn = document.createElement('button');
    downloadBtn.className = 'code-action-btn download-btn';
    downloadBtn.innerText = '📥 下載檔案';
    downloadBtn.addEventListener('click', () => {
      const codeText = codeEl?.innerText || '';
      const ext = getFileExtension(langClass);
      
      // 建立 Blob 與虛擬下載鏈結
      const blob = new Blob([codeText], { type: 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `generated_code_${Date.now()}.${ext}`; // 自動命名
      document.body.appendChild(a);
      a.click();
      
      // 釋放記憶體
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

<style>
/* =========================================================================
   🎨 高質感 Cyber Blue 淡藍色程式碼區塊樣式表
   ========================================================================= */
.markdown-body {
  line-height: 1.6;
}

/* 🎯 大塊程式碼區塊基底：雅致的低飽和淡藍灰底 */
.markdown-body pre {
  background-color: #f0f5fa !important; 
  border: 1px solid #d0e1f0 !important;
  padding: 1rem;
  border-radius: 12px;
  overflow-x: auto;
  margin: 0.8em 0;
}

/* 程式碼字體與顏色微調 */
.markdown-body code {
  font-family: 'Fira Code', Consolas, Monaco, monospace;
  font-size: 14px;
  color: #1e3a8a !important; /* 深科技藍字體 */
}

/* 🎯 頂部控制列：高質感亮色淡藍橫條 */
.code-action-bar {
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
.code-lang-tag {
  font-size: 11px;
  font-weight: 700;
  color: #60a5fa;
  letter-spacing: 0.5px;
}

/* 按鈕群組 */
.code-btn-group {
  display: flex;
  gap: 8px;
}

/* 極簡科技感操作按鈕 */
.code-action-btn {
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

.code-action-btn:hover {
  background-color: #d0e6f7;
  color: #0d47a1;
}

/* 下載按鈕特別強調色 */
.download-btn {
  color: #2e7d32; /* 沉穩優雅的工程綠 */
}
.download-btn:hover {
  background-color: #c8e6c9;
  color: #1b5e20;
}

/* 🎯 句子內夾帶的單行小程式碼（例如 `app.py`） */
.markdown-body :not(pre) > code {
  background-color: #e3f2fd;
  color: #0d47a1;
  padding: 0.2em 0.4em;
  border-radius: 6px;
  font-size: 13px;
  border: 1px solid #bbdefb;
}

/* 清除外邊距干擾 */
.markdown-body p:first-child { margin-top: 0; }
.markdown-body p:last-child { margin-bottom: 0; }
</style>
