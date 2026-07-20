<!-- src/components/ImportSkillModal.vue -->
<template>
  <el-dialog
    v-model="visible"
    title="📥 匯入技能"
    width="440px"
    :close-on-click-modal="false"
    append-to-body
    class="rounded-2xl shadow-2xl"
    @open="handleOpen"
  >
    <div class="flex flex-col gap-5 py-2">
      <div class="bg-[#e0f2fe] border border-[#7dd3fc] p-4 rounded-xl flex gap-3 items-start">
        <span class="text-2xl mt-0.5">💡</span>
        <p class="text-xs text-[#0369a1] leading-relaxed">
          上傳一份 <code>SKILL.md</code> 檔案，透過 hermes 原生指令 <code>hermes skills install</code> 安裝進目前這個 Agent。v1 僅支援單一 SKILL.md 檔案，尚不支援含附件的多檔案技能包。
        </p>
      </div>

      <el-form label-position="top">
        <el-form-item label="✨ 技能名稱" required>
          <el-input v-model="skillName" placeholder="請輸入技能名稱..." class="w-full !rounded-xl" />
        </el-form-item>

        <el-form-item label="📄 選擇 SKILL.md 檔案" required>
          <el-upload
            drag
            :auto-upload="false"
            :limit="1"
            accept=".md"
            :on-change="handleFileChange"
            :on-remove="() => (selectedFile = null)"
            class="w-full"
          >
            <div class="py-4 text-sm text-[#9ca3af]">拖曳或點擊上傳 .md 檔案</div>
          </el-upload>
        </el-form-item>
      </el-form>
    </div>

    <template #footer>
      <div class="flex justify-end gap-2 border-t border-[#f3f4f6] pt-4">
        <el-button @click="visible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="isSubmitting"
          :disabled="!skillName.trim() || !selectedFile"
          @click="submitImport"
        >
          📥 開始匯入
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

const skillName = ref('');
const selectedFile = ref(null);
const isSubmitting = ref(false);

const handleOpen = () => {
  skillName.value = '';
  selectedFile.value = null;
};

const handleFileChange = (uploadFile) => {
  selectedFile.value = uploadFile.raw;
};

const submitImport = async () => {
  if (!chatStore.currentAgentId) {
    ElMessage.warning('目前不在任何 Agent 的辦公室中，無法匯入技能。');
    return;
  }
  try {
    isSubmitting.value = true;
    await chatStore.importSkillAction(chatStore.currentAgentId, skillName.value.trim(), selectedFile.value);
    ElMessage.success(`🎉 技能「${skillName.value}」已成功安裝！`);
    visible.value = false;
  } catch (err) {
    console.error('匯入技能失敗:', err);
    ElMessage.error(`匯入失敗：${err?.response?.data?.error || err?.message || '未知錯誤'}`);
  } finally {
    isSubmitting.value = false;
  }
};
</script>
