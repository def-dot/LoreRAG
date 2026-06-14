import request from './request'

export interface DocumentItem {
  file_name: string
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
    '/rag/upload',
    form,
  )
}

// 获取文档列表
export function getDocuments() {
  return request.get<{ code: number; msg: string; data: { items: DocumentItem[]; total: number } }>(
    '/rag/documents',
  )
}

// 删除文档
export function deleteDocument(fileName: string) {
  return request.delete<{ code: number; msg: string; data: { deleted_chunks: number } }>(
    `/rag/documents/${encodeURIComponent(fileName)}`,
  )
}

// 知识库检索
export function searchKnowledge(query: string, topK = 5) {
  return request.post<{ code: number; msg: string; data: { results: SearchResult[]; total: number } }>(
    '/rag/search',
    { query, top_k: topK },
  )
}
