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
    documents.value = res.data.data.items
  } finally {
    loading.value = false
  }
}

async function handleUpload(options: { file: UploadFile }) {
  const file = options.file.raw
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
  await ElMessageBox.confirm(`确定删除文档「${row.file_name}」及其所有切片？`, '删除确认', { type: 'warning' })
  try {
    await deleteDocument(row.file_name)
    ElMessage.success('删除成功')
    await fetchDocuments()
  } catch {
    // interceptor handles error message
  }
}

onMounted(fetchDocuments)
</script>

<template>
  <div class="knowledge-page">
    <!-- 上传区 -->
    <el-card class="upload-card" shadow="never">
      <el-upload drag :auto-upload="false" :show-file-list="false" :on-change="handleUpload" accept=".pdf,.docx,.pptx"
        :disabled="uploading">
        <div class="upload-content">
          <el-icon class="upload-icon" :size="48">
            <UploadFilled />
          </el-icon>
          <p class="upload-text">拖拽文件到此处，或 <em>点击上传</em></p>
          <p class="upload-tip">支持 PDF / DOCX / PPTX 格式</p>
        </div>
      </el-upload>
    </el-card>

    <!-- 文档列表 -->
    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="card-header">
          <span>已入库文档</span>
          <el-button :icon="Refresh" text @click="fetchDocuments" :loading="loading">刷新</el-button>
        </div>
      </template>

      <el-table :data="documents" v-loading="loading" stripe empty-text="暂无文档，请上传">
        <el-table-column label="文件名" min-width="200">
          <template #default="{ row }">
            <div class="file-name">
              <el-icon>
                <Document />
              </el-icon>
              <span>{{ row.file_name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="chunk_count" label="切片数" width="100" align="center" />
        <el-table-column label="页码范围" width="200">
          <template #default="{ row }">
            <template v-if="row.page_numbers?.length">
              {{ row.page_numbers[0] }} - {{ row.page_numbers[row.page_numbers.length - 1] }}
            </template>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" align="center">
          <template #default="{ row }">
            <el-button :icon="Delete" type="danger" text size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.knowledge-page {
  max-width: 960px;
  margin: 0 auto;
}

.upload-card {
  margin-bottom: 20px;
}

.upload-card :deep(.el-upload-dragger) {
  padding: 40px 20px;
  border-radius: 12px;
}

.upload-content {
  text-align: center;
}

.upload-icon {
  color: #c0c4cc;
  margin-bottom: 12px;
}

.upload-text {
  color: #666;
  font-size: 14px;
}

.upload-text em {
  color: #409eff;
  font-style: normal;
}

.upload-tip {
  color: #999;
  font-size: 12px;
  margin-top: 4px;
}

.table-card :deep(.el-card__header) {
  padding: 12px 20px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
}

.file-name {
  display: flex;
  align-items: center;
  gap: 6px;
}

.text-muted {
  color: #c0c4cc;
}
</style>
