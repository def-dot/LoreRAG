import { defineStore } from 'pinia'
import { ref } from 'vue'
import { searchKnowledge, type SearchResult } from '../api/rag'

export type SearchMode = 'bm25' | 'vector' | 'hybrid'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  results?: SearchResult[]
  loading?: boolean
  tokens?: string[]
  mode?: SearchMode
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const mode = ref<SearchMode>('hybrid')
  const useLLM = ref(false)

  async function sendQuery(query: string) {
    messages.value.push({ role: 'user', content: query })

    const assistantMsg: ChatMessage = { role: 'assistant', content: '', loading: true, userQuery: query, mode: mode.value }
    messages.value.push(assistantMsg)

    try {
      const res = await searchKnowledge(query, 5, mode.value)
      const { results, tokens } = res.data.data

      const last = messages.value[messages.value.length - 1]
      last.loading = false
      last.results = results
      last.tokens = tokens
      last.content = results.length
        ? `找到 ${results.length} 条相关内容`
        : '未找到相关内容'
    } catch {
      const last = messages.value[messages.value.length - 1]
      last.loading = false
      last.content = '检索失败，请重试'
    }
  }

  function clear() {
    messages.value = []
  }

  return { messages, mode, useLLM, sendQuery, clear }
})
