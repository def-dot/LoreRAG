import { defineStore } from 'pinia'
import { ref } from 'vue'
import { searchKnowledge, type SearchResult } from '../api/rag'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  results?: SearchResult[]
  loading?: boolean
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])

  async function sendQuery(query: string) {
    // 添加用户消息
    messages.value.push({ role: 'user', content: query })

    // 添加 loading 占位
    const assistantMsg: ChatMessage = { role: 'assistant', content: '', loading: true }
    messages.value.push(assistantMsg)

    try {
      const res = await searchKnowledge(query)
      const results = res.data.data.results

      // 更新助手消息
      const last = messages.value[messages.value.length - 1]
      last.loading = false
      last.results = results
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

  return { messages, sendQuery, clear }
})
