<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, Delete, Refresh, Document } from '@element-plus/icons-vue'
import type { UploadFile } from 'element-plus'
import { uploadDocument, getDocuments, deleteDocument, type DocumentItem } from '../api/rag'

const documents = ref<DocumentItem[]>([])
const loading = ref(false)
const uploading = ref(false)

async function fetchDocuments() {
  loading.value = true
  try {
    const res = await getDocuments()
    documents.value = res.data.items
  } finally {
    loading.value = false
  }
}

async function handleUpload(uploadFile: UploadFile) {
  const file = uploadFile.raw
  if (!file) return

  const ext = file.name.split('.').pop()?.toLowerCase()
  if (!['pdf', 'docx', 'pptx'].includes(ext || '')) {
    ElMessage.error('仅支持 PDF / DOCX / PPTX 格式')
    return
  }

  uploading.value = true
  try {
    await uploadDocument(file)
    ElMessage.success(`${file.name} 已上传，后台正在处理`)
    await fetchDocuments()
  } finally {
    uploading.value = false
  }
}

async function handleDelete(row: DocumentItem) {
  await ElMessageBox.confirm(`确定删除文档「${row.file_name}」及其所有切片？`, '删除确认', {
    type: 'warning',
  })
  try {
    await deleteDocument(row.file_name)
    ElMessage.success('删除成功')
    await fetchDocuments()
  } catch {
    // interceptor handles error message
  }
}

function formatTime(value: string | null): string {
  if (!value) return ''
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

onMounted(fetchDocuments)
</script>

<template>
  <div class="knowledge-page">
    <!-- 上传区 -->
    <el-card class="upload-card" shadow="never">
      <el-upload
        drag
        :auto-upload="false"
        :show-file-list="false"
        :on-change="handleUpload"
        accept=".pdf,.docx,.pptx"
        :disabled="uploading"
      >
        <div class="upload-content">
          <div class="upload-icon-wrap">
            <el-icon :size="26"><UploadFilled /></el-icon>
          </div>
          <p class="upload-text">拖拽文件到此处，或 <em>点击上传</em></p>
          <div class="upload-formats">
            <span class="fmt">PDF</span>
            <span class="fmt">DOCX</span>
            <span class="fmt">PPTX</span>
          </div>
        </div>
      </el-upload>
    </el-card>

    <!-- 文档列表 -->
    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="card-header">
          <div class="card-title">
            <span class="title-text">已入库文档</span>
            <span class="count-chip">{{ documents.length }}</span>
          </div>
          <el-button :icon="Refresh" text @click="fetchDocuments" :loading="loading">刷新</el-button>
        </div>
      </template>

      <el-table :data="documents" v-loading="loading" stripe empty-text="暂无文档，请上传">
        <el-table-column label="文件名" min-width="220">
          <template #default="{ row }">
            <div class="file-name">
              <el-icon class="file-icon"><Document /></el-icon>
              <span class="file-text">{{ row.file_name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="chunk_count" label="切片数" width="90" align="center" />
        <el-table-column label="页码范围" width="160">
          <template #default="{ row }">
            <template v-if="row.page_numbers?.length">
              {{ row.page_numbers[0] }} - {{ row.page_numbers[row.page_numbers.length - 1] }}
            </template>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="上传时间" width="150">
          <template #default="{ row }">
            <span v-if="row.created_at" class="time-cell">{{ formatTime(row.created_at) }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="开始解析" width="150">
          <template #default="{ row }">
            <span v-if="row.parse_started_at" class="time-cell">{{ formatTime(row.parse_started_at) }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="解析完成" width="150">
          <template #default="{ row }">
            <span v-if="row.parse_completed_at" class="time-cell">{{ formatTime(row.parse_completed_at) }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90" align="center">
          <template #default="{ row }">
            <el-button :icon="Delete" type="danger" text size="small" @click="handleDelete(row)"
              >删除</el-button
            >
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.knowledge-page {
  max-width: 1180px;
  margin: 0 auto;
}

/* ---------------- Upload ---------------- */
.upload-card {
  margin-bottom: 20px;
}

.upload-card :deep(.el-card__body) {
  padding: 12px;
}

.upload-card :deep(.el-upload),
.upload-card :deep(.el-upload-dragger) {
  width: 100%;
}

.upload-card :deep(.el-upload-dragger) {
  padding: 32px 20px;
  border-radius: 8px;
  border-color: var(--border-strong);
  background: var(--surface-2);
  transition: border-color 0.2s ease, background 0.2s ease;
}

.upload-card :deep(.el-upload-dragger:hover) {
  border-color: var(--brand);
  background: var(--brand-soft);
}

.upload-content {
  text-align: center;
}

.upload-icon-wrap {
  width: 52px;
  height: 52px;
  margin: 0 auto 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  background: var(--brand-soft);
  color: var(--brand);
  transition: background 0.2s ease;
}

.upload-card :deep(.el-upload-dragger:hover) .upload-icon-wrap {
  background: #ffffff;
}

.upload-text {
  color: var(--ink-2);
  font-size: 14px;
}

.upload-text em {
  color: var(--brand);
  font-style: normal;
  font-weight: 600;
}

.upload-formats {
  margin-top: 10px;
  display: flex;
  gap: 6px;
  justify-content: center;
}

.fmt {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--ink-3);
  padding: 2px 8px;
  border: 1px solid var(--border-strong);
  border-radius: 4px;
  background: var(--surface);
}

/* ---------------- Table card ---------------- */
.table-card :deep(.el-card__header) {
  padding: 14px 20px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 10px;
}

.title-text {
  font-weight: 600;
  color: var(--ink);
  font-size: 15px;
}

.count-chip {
  min-width: 22px;
  height: 22px;
  padding: 0 7px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  color: var(--brand);
  background: var(--brand-soft);
  border-radius: 11px;
}

/* ---------------- Table cells ---------------- */
.file-name {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.file-icon {
  color: var(--ink-4);
  flex-shrink: 0;
}

.file-text {
  color: var(--ink);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.time-cell {
  font-variant-numeric: tabular-nums;
  font-size: 12.5px;
  color: var(--ink-3);
  white-space: nowrap;
}

.text-muted {
  color: var(--ink-4);
}

/* table spacing refinement */
.table-card :deep(.el-table) {
  font-size: 13.5px;
}

.table-card :deep(.el-table .cell) {
  line-height: 1.5;
}

.table-card :deep(.el-table td.el-table__cell) {
  padding: 11px 0;
}
</style>
