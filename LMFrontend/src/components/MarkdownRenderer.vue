<template>
  <!-- 使用 v-html 渲染解析後的 Markdown，並加上渲染專用 Class -->
  <div class="markdown-body" v-html="renderedContent" ref="contentRef"></div>
</template>

<script setup>
import { computed, ref, onMounted, onUpdated, nextTick } from 'vue'
import { Marked } from 'marked'
import Prism from 'prismjs'
// 引入 Prism 的經典深色主題（可換成其他主題，如 prism-tomorrow）
import 'prismjs/themes/prism-tomorrow.css'

// 接收來自父元件（對話房間）的 AI 純文字訊息
const props = defineProps({
  content: {
    type: String,
    required: true
  }
})

const contentRef = ref(null)

// 1. 初始化 Marked 解析器
const marked = new Marked()

// 2. 計算屬性：將純文字即時轉成 HTML 結構
const renderedContent = computed(() => {
  if (!props.content) return ''
  return marked.parse(props.content)
})

// 3. 核心防禦：重新渲染程式碼高亮並綁定複製按鈕
const highlightAndAddCopyButtons = async () => {
  await nextTick()
  if (!contentRef.value) return

  // 讓 Prism 掃描並高亮所有的 <code> 區塊
  Prism.highlightAllUnder(contentRef.value)

  // 撈出畫面中所有的 <pre> 區塊，動態塞入複製按鈕
  const preElements = contentRef.value.querySelectorAll('pre')
  
  preElements.forEach((pre) => {
    // 防止重複建立按鈕
    if (pre.querySelector('.copy-btn')) return

    pre.style.position = 'relative' // 讓按鈕可以定位在右上角

    const button = document.createElement('button')
    button.className = 'copy-btn'
    button.innerText = '📋 複製'

    // 點擊按鈕時的複製邏輯
    button.addEventListener('click', async () => {
      const codeText = pre.querySelector('code')?.innerText || ''
      try {
        await navigator.clipboard.writeText(codeText)
        button.innerText = '✅ 已複製！'
        setTimeout(() => { button.innerText = '📋 複製' }, 2000)
      } catch (err) {
        button.innerText = '❌ 失敗'
      }
    })

    pre.appendChild(button)
  })
}

// 生命週期守衛：確保資料進來或更新時，灰色框與按鈕都正常運作
onMounted(highlightAndAddCopyButtons)
onUpdated(highlightAndAddCopyButtons)
</script>

<style>
/* 🧠 樣式設計：完美契合你的高防禦型系統外觀 */
.markdown-body {
  line-height: 1.6;
  color: #333;
}

/* 這是你想要的程式碼灰色背景區塊 */
.markdown-body pre {
  background-color: #2d2d2d !important; /* 強制使用深灰底色 */
  padding: 1rem;
  border-radius: 6px;
  overflow-x: auto;
  margin: 1em 0;
}

/* 讓單行小程式碼也有小灰底 */
.markdown-body :not(pre) > code {
  background-color: #f5f5f5;
  color: #d63200;
  padding: 0.2em 0.4em;
  border-radius: 3px;
  font-family: monospace;
}

/* 右上角複製按鈕樣式 */
.copy-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  background: rgba(255, 255, 255, 0.2);
  border: none;
  color: #fff;
  padding: 4px 8px;
  font-size: 12px;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.2s;
}

.copy-btn:hover {
  background: rgba(255, 255, 255, 0.4);
}
</style>
