import request from './request'

export interface DocumentItem {
  id: number
  file_name: string
  file_size: number | null
  status: string
  error_message: string | null
  chunk_count: number
  page_numbers: number[]
  created_at: string | null
  parse_started_at: string | null
  parse_completed_at: string | null
}

export interface SearchResult {
  chunk_id: number
  file_name: string
  page_numbers: number[]
  heading_context: string
  content: string
  score: number
}

// 上传文档
export function uploadDocument(file: File) {
  const form = new FormData()
  form.append('file', file)
  return request.post<{ code: number; msg: string; data: { file_name: string; status: string } }>(
    '/document/upload',
    form,
  )
}

// 获取文档列表
export function getDocuments() {
  return request.get<{ code: number; msg: string; data: { items: DocumentItem[]; total: number } }>(
    '/document/',
  )
}

// 删除文档
export function deleteDocument(documentId: number) {
  return request.delete<{ code: number; msg: string; data: { deleted_chunks: number; file_name: string } }>(
    `/document/${documentId}`,
  )
}

// 取消解析
export function cancelDocument(documentId: number) {
  return request.post(`/document/${documentId}/cancel`)
}

// 重试解析
export function retryDocument(documentId: number) {
  return request.post(`/document/${documentId}/retry`)
}

// 下载原始文件
export function getDownloadUrl(documentId: number): string {
  return `/api/v1/document/${documentId}/download`
}

// 文档切片
export interface ChunkItem {
  id: number
  document_id: number
  page_numbers: number[]
  heading_context: string
  raw_content: string
}

export function getDocumentChunks(documentId: number) {
  return request.get<{ code: number; msg: string; data: { items: ChunkItem[]; total: number } }>(
    `/document/${documentId}/chunks`,
  )
}

// 文档每页解析结果
export interface PageData {
  page_no: number
  width: number
  height: number
  markdown: string
  table_count: number
  picture_count: number
}

export function getDocumentPages(documentId: number) {
  return request.get<{ code: number; msg: string; data: { pages: PageData[]; total: number } }>(
    `/document/${documentId}/pages`,
  )
}

// 知识库检索
export function searchKnowledge(query: string, topK = 5, mode = 'hybrid') {
  return request.post<{ code: number; msg: string; data: { results: SearchResult[]; total: number } }>(
    '/rag/search',
    { query, top_k: topK, mode },
  )
}
