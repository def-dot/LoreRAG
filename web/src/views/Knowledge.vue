<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, Delete, Refresh, RefreshRight, VideoPause, Document, Download, View } from '@element-plus/icons-vue'
import type { UploadFile } from 'element-plus'
import MarkdownIt from 'markdown-it'
import { uploadDocument, getDocuments, deleteDocument, cancelDocument, retryDocument, getDocumentChunks, getDownloadUrl, getDocumentPages, type DocumentItem, type ChunkItem, type PageData } from '../api/rag'

const md = new MarkdownIt({ html: false, breaks: true, linkify: true })

const documents = ref<DocumentItem[]>([])
const loading = ref(false)
const uploading = ref(false)
let pollTimer: ReturnType<typeof setInterval> | null = null

// --- chunk drawer ---
const chunkDrawer = ref(false)
const chunkLoading = ref(false)
const chunks = ref<ChunkItem[]>([])
const chunkDocName = ref('')

async function openChunks(row: DocumentItem) {
  if (row.status === 'failed') return
  chunkDocName.value = row.file_name
  chunkDrawer.value = true
  chunkLoading.value = true
  try {
    const res = await getDocumentChunks(row.id)
    chunks.value = res.data.items
  } catch {
    chunks.value = []
  } finally {
    chunkLoading.value = false
  }
}

// --- pages dialog ---
const pagesDialog = ref(false)
const pagesLoading = ref(false)
const pages = ref<PageData[]>([])
const currentPage = ref(0)
const pagesDocName = ref('')
const pageContent = ref<HTMLElement>()

function renderMarkdown(text: string): string {
  return md.render(text)
}

async function openPages(row: DocumentItem) {
  pagesDocName.value = row.file_name
  pagesDialog.value = true
  pagesLoading.value = true
  currentPage.value = 0
  try {
    const res = await getDocumentPages(row.id)
    pages.value = res.data.pages
  } catch {
    pages.value = []
  } finally {
    pagesLoading.value = false
  }
}

function selectPage(idx: number) {
  currentPage.value = idx
  nextTick(() => {
    pageContent.value?.scrollTo({ top: 0, behavior: 'smooth' })
  })
}

function prevPage() {
  if (currentPage.value > 0) selectPage(currentPage.value - 1)
}

function nextPage() {
  if (currentPage.value < pages.value.length - 1) selectPage(currentPage.value + 1)
}

const currentPageData = computed(() => pages.value[currentPage.value] ?? null)

const hasPending = computed(() =>
  documents.value.some(d => d.status === 'pending' || d.status === 'processing')
)

const statusMap: Record<string, { label: string; type: '' | 'success' | 'warning' | 'danger' | 'info' }> = {
  pending:    { label: '排队中', type: 'info' },
  processing: { label: '解析中', type: 'warning' },
  completed:  { label: '已完成', type: 'success' },
  failed:     { label: '失败',   type: 'danger' },
}

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

async function handleCancel(row: DocumentItem) {
  try {
    await cancelDocument(row.id)
    ElMessage.success('已取消')
    await fetchDocuments()
  } catch {
    // interceptor handles error message
  }
}

async function handleRetry(row: DocumentItem) {
  try {
    await retryDocument(row.id)
    ElMessage.success('已重新加入队列')
    await fetchDocuments()
  } catch {
    // interceptor handles error message
  }
}

async function handleDelete(row: DocumentItem) {
  await ElMessageBox.confirm(`确定删除文档「${row.file_name}」及其所有切片？`, '删除确认', {
    type: 'warning',
  })
  try {
    await deleteDocument(row.id)
    ElMessage.success('删除成功')
    await fetchDocuments()
  } catch {
    // interceptor handles error message
  }
}

function formatFileSize(bytes: number | null): string {
  if (!bytes) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatTime(value: string | null): string {
  if (!value) return ''
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function startPolling() {
  pollTimer = setInterval(async () => {
    if (!hasPending.value) return
    try {
      const res = await getDocuments()
      documents.value = res.data.items
    } catch { /* silent */ }
  }, 10000)
}

onMounted(async () => {
  await fetchDocuments()
  startPolling()
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
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

      <el-table :data="documents" v-loading="loading" stripe empty-text="暂无文档，请上传" @row-click="openChunks">
        <el-table-column label="文件名" min-width="220">
          <template #default="{ row }">
            <div class="file-name">
              <el-icon class="file-icon"><Document /></el-icon>
              <span class="file-text">{{ row.file_name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="大小" width="90" align="right">
          <template #default="{ row }">
            <span class="size-cell">{{ formatFileSize(row.file_size) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tooltip
              v-if="row.status === 'failed' && row.error_message"
              :content="row.error_message"
              placement="top"
              :show-after="200"
            >
              <el-tag type="danger" size="small" effect="light">失败</el-tag>
            </el-tooltip>
            <el-tag v-else :type="statusMap[row.status]?.type ?? 'info'" size="small" effect="light">
              {{ statusMap[row.status]?.label ?? row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="chunk_count" label="切片数" width="90" align="center" />

        <el-table-column label="上传时间" width="150">
          <template #default="{ row }">
            <span v-if="row.created_at" class="time-cell">{{ formatTime(row.created_at) }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="170" align="center">
          <template #default="{ row }">
            <span class="action-slot">
              <template v-if="row.status === 'pending' || row.status === 'processing'">
                <el-tooltip content="取消">
                  <el-button :icon="VideoPause" type="warning" text size="small" @click.stop="handleCancel(row)" />
                </el-tooltip>
              </template>
              <template v-else-if="row.status === 'failed'">
                <el-tooltip content="重试">
                  <el-button :icon="RefreshRight" type="primary" text size="small" @click.stop="handleRetry(row)" />
                </el-tooltip>
              </template>
              <template v-else-if="row.status === 'completed'">
                <el-tooltip content="解析结果">
                  <el-button :icon="View" type="primary" text size="small" @click.stop="openPages(row)" />
                </el-tooltip>
              </template>
            </span>
            <span class="action-slot">
              <a :href="getDownloadUrl(row.id)" class="download-link" @click.stop>
                <el-tooltip content="下载">
                  <el-button :icon="Download" type="primary" text size="small" />
                </el-tooltip>
              </a>
            </span>
            <span class="action-slot">
              <el-tooltip content="删除">
                <el-button :icon="Delete" type="danger" text size="small" @click.stop="handleDelete(row)" />
              </el-tooltip>
            </span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 切片详情抽屉 -->
    <el-drawer
      v-model="chunkDrawer"
      :title="`切片详情 — ${chunkDocName}`"
      size="560px"
      direction="rtl"
    >
      <div v-loading="chunkLoading" class="chunk-list">
        <template v-if="!chunkLoading && chunks.length === 0">
          <div class="chunk-empty">该文档暂无切片数据</div>
        </template>
        <div
          v-for="(chunk, idx) in chunks"
          :key="chunk.id"
          class="chunk-card"
        >
          <div class="chunk-header">
            <span class="chunk-index">#{{ idx + 1 }}</span>
            <el-tag
              v-if="chunk.page_numbers.length"
              size="small"
              effect="plain"
              round
            >
              第 {{ chunk.page_numbers.join(', ') }} 页
            </el-tag>
            <span class="chunk-heading">{{ chunk.heading_context }}</span>
          </div>
          <div class="chunk-body">
            <pre class="chunk-text">{{ chunk.raw_content }}</pre>
          </div>
        </div>
      </div>
    </el-drawer>

    <!-- 解析结果弹窗 -->
    <el-dialog
      v-model="pagesDialog"
      :title="`解析结果 — ${pagesDocName}`"
      width="900px"
      top="3vh"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <div v-loading="pagesLoading" class="pages-dialog">
        <template v-if="!pagesLoading && pages.length === 0">
          <div class="pages-empty">暂无解析结果数据</div>
        </template>
        <template v-else-if="!pagesLoading && currentPageData">
          <div class="pages-layout">
            <!-- 左侧页码导航 -->
            <div class="pages-nav">
              <div
                v-for="(p, idx) in pages"
                :key="p.page_no"
                class="page-thumb"
                :class="{ active: idx === currentPage }"
                @click="selectPage(idx)"
              >
                <span class="page-no">P{{ p.page_no }}</span>
                <span class="page-meta">
                  <template v-if="p.table_count">{{ p.table_count }} 表</template>
                  <template v-if="p.picture_count">{{ p.picture_count }} 图</template>
                </span>
              </div>
            </div>

            <!-- 右侧内容 -->
            <div class="pages-content" ref="pageContent">
              <div class="page-info">
                <span>第 {{ currentPageData.page_no }} 页</span>
                <span class="page-size">{{ currentPageData.width.toFixed(0) }} × {{ currentPageData.height.toFixed(0) }}</span>
                <span v-if="currentPageData.table_count">{{ currentPageData.table_count }} 个表格</span>
                <span v-if="currentPageData.picture_count">{{ currentPageData.picture_count }} 张图片</span>
              </div>
              <div
                class="markdown-body"
                v-html="renderMarkdown(currentPageData.markdown)"
              />
            </div>
          </div>
        </template>
      </div>

      <template #footer>
        <div class="dialog-footer">
          <div class="page-nav-btns">
            <el-button :disabled="currentPage === 0" @click="prevPage">上一页</el-button>
            <span class="page-indicator">{{ currentPage + 1 }} / {{ pages.length }}</span>
            <el-button :disabled="currentPage >= pages.length - 1" @click="nextPage">下一页</el-button>
          </div>
          <el-button @click="pagesDialog = false">关闭</el-button>
        </div>
      </template>
    </el-dialog>
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

.action-slot {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 24px;
}

.download-link {
  text-decoration: none;
  color: inherit;
}

.time-cell {
  font-variant-numeric: tabular-nums;
  font-size: 12.5px;
  color: var(--ink-3);
  white-space: nowrap;
}

.size-cell {
  font-size: 12.5px;
  color: var(--ink-3);
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

.table-card :deep(.el-table__body tr) {
  cursor: pointer;
}

/* ---------------- Chunk drawer ---------------- */
.chunk-list {
  min-height: 200px;
}

.chunk-empty {
  text-align: center;
  color: var(--ink-3);
  padding: 48px 0;
  font-size: 14px;
}

.chunk-card {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px;
  margin-bottom: 12px;
  transition: border-color 0.2s ease;
}

.chunk-card:hover {
  border-color: var(--border-strong);
}

.chunk-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}

.chunk-index {
  font-size: 12px;
  font-weight: 700;
  color: var(--ink-4);
  letter-spacing: 0.02em;
  min-width: 24px;
}

.chunk-heading {
  font-size: 12.5px;
  font-weight: 500;
  color: var(--ink-3);
}

.chunk-body {
  background: var(--surface-2);
  border-radius: 6px;
  padding: 12px 14px;
  overflow-x: auto;
}

.chunk-text {
  margin: 0;
  font-family: var(--font-sans);
  font-size: 13px;
  line-height: 1.7;
  color: var(--ink-2);
  white-space: pre-wrap;
  word-break: break-word;
}

/* ---------------- Pages dialog ---------------- */
.pages-dialog {
  min-height: 400px;
}

.pages-empty {
  text-align: center;
  color: var(--ink-3);
  padding: 64px 0;
  font-size: 14px;
}

.pages-layout {
  display: flex;
  gap: 0;
  height: 62vh;
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}

.pages-nav {
  width: 120px;
  flex-shrink: 0;
  overflow-y: auto;
  background: var(--surface-2);
  border-right: 1px solid var(--border);
  padding: 8px;
}

.page-thumb {
  padding: 10px 8px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 4px;
  transition: background 0.15s;
}

.page-thumb:hover {
  background: var(--surface);
}

.page-thumb.active {
  background: var(--brand-soft);
}

.page-no {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
}

.page-thumb.active .page-no {
  color: var(--brand);
}

.page-meta {
  display: block;
  font-size: 11px;
  color: var(--ink-4);
  margin-top: 2px;
}

.pages-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px 24px;
}

.page-info {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
  font-size: 12.5px;
  color: var(--ink-3);
  padding-bottom: 12px;
  margin-bottom: 16px;
  border-bottom: 1px solid var(--border);
}

.page-size {
  font-variant-numeric: tabular-nums;
}

.markdown-body {
  font-size: 14px;
  line-height: 1.8;
  color: var(--ink-2);
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  color: var(--ink);
  margin-top: 1.2em;
  margin-bottom: 0.4em;
}

.markdown-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
  font-size: 13px;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid var(--border);
  padding: 6px 10px;
  text-align: left;
}

.markdown-body :deep(th) {
  background: var(--surface-2);
  font-weight: 600;
}

.markdown-body :deep(p) {
  margin: 0.5em 0;
}

.markdown-body :deep(img) {
  max-width: 100%;
}

.dialog-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.page-nav-btns {
  display: flex;
  align-items: center;
  gap: 10px;
}

.page-indicator {
  font-size: 13px;
  font-variant-numeric: tabular-nums;
  color: var(--ink-3);
  min-width: 60px;
  text-align: center;
}
</style>
