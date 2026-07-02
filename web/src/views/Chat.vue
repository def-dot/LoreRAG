<script setup lang="ts">
import { ref, nextTick, computed } from 'vue'
import { Promotion, ChatDotRound } from '@element-plus/icons-vue'
import { useChatStore } from '../stores/chat'
import MarkdownIt from 'markdown-it'

const md = new MarkdownIt({ html: false, breaks: true, linkify: true })

const chatStore = useChatStore()
const inputQuery = ref('')
const chatContainer = ref<HTMLElement>()

function highlightTokens(text: string, tokens: string[]): string {
  if (!tokens.length) return text
  const escaped = tokens
    .sort((a, b) => b.length - a.length)
    .map(t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  return text.replace(new RegExp(escaped.join('|'), 'g'), '<mark>$&</mark>')
}

const modeOptions = [
  { label: '混合', value: 'hybrid' },
  { label: 'BM25', value: 'bm25' },
  { label: '向量', value: 'vector' },
] as const

const messages = computed(() => chatStore.messages)
const canSend = computed(() => inputQuery.value.trim() && !messages.value.some((m) => m.loading))

function renderMarkdown(text: string): string {
  return md.render(text)
}

function formatScore(score: number): string {
  return (score * 100).toFixed(1) + '%'
}

async function sendQuery() {
  const query = inputQuery.value.trim()
  if (!query) return
  inputQuery.value = ''

  await chatStore.sendQuery(query)
  await nextTick()
  scrollToBottom()
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendQuery()
  }
}

function scrollToBottom() {
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
}

function clearChat() {
  chatStore.clear()
}
</script>

<template>
  <div class="chat-page">
    <div ref="chatContainer" class="chat-messages">
      <div v-if="messages.length === 0" class="empty-state">
        <div class="empty-icon">
          <el-icon :size="28"><ChatDotRound /></el-icon>
        </div>
        <p class="empty-title">向知识库提问</p>
        <p class="empty-tip">输入问题，系统将检索最相关的文档切片并返回答案与来源</p>
      </div>

      <div v-for="(msg, i) in messages" :key="i" :class="['message-row', msg.role]">
        <div class="message-bubble">
          <template v-if="msg.role === 'user'">
            <p>{{ msg.content }}</p>
          </template>

          <template v-else>
            <div v-if="msg.loading" class="loading-dots">
              <span></span><span></span><span></span>
            </div>
            <template v-else>
              <p class="result-summary">{{ msg.content }}</p>

              <div v-if="msg.results?.length" class="result-list">
                <div v-for="(r, ri) in msg.results" :key="ri" class="result-card">
                  <div class="result-header">
                    <div class="result-source">
                      <el-tag size="small" type="info">{{ r.file_name }}</el-tag>
                      <el-tag v-if="r.page_numbers?.length" size="small">P{{ r.page_numbers[0] }}</el-tag>
                    </div>
                    <span class="result-score">相关度 {{ formatScore(r.score) }}</span>
                  </div>
                  <div v-if="r.heading_context && r.heading_context !== 'Root'" class="result-heading">
                    {{ r.heading_context }}
                  </div>
                  <div class="result-content" v-html="chatStore.mode === 'bm25' && msg.tokens ? highlightTokens(r.content, msg.tokens) : renderMarkdown(r.content)"></div>
                </div>
              </div>
            </template>
          </template>
        </div>
      </div>
    </div>

    <div class="chat-input-area">
      <div class="mode-bar">
        <el-radio-group v-model="chatStore.mode" size="small">
          <el-radio-button v-for="m in modeOptions" :key="m.value" :value="m.value">
            {{ m.label }}
          </el-radio-button>
        </el-radio-group>
      </div>
      <el-input
        v-model="inputQuery"
        type="textarea"
        :rows="2"
        placeholder="输入你的问题..."
        resize="none"
        @keydown="handleKeydown"
        :disabled="messages.some((m) => m.loading)"
      />
      <div class="input-actions">
        <el-button text size="small" @click="clearChat" :disabled="messages.length === 0">清空对话</el-button>
        <el-button type="primary" :icon="Promotion" :disabled="!canSend" @click="sendQuery">发送</el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 60px - 40px);
  max-width: 900px;
  margin: 0 auto;
  width: 100%;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px 0;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--ink-3);
}

.empty-icon {
  width: 60px;
  height: 60px;
  margin-bottom: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 16px;
  background: var(--brand-soft);
  color: var(--brand);
}

.empty-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--ink-2);
  margin-bottom: 8px;
}

.empty-tip {
  font-size: 13px;
  color: var(--ink-4);
}

.message-row {
  display: flex;
  margin-bottom: 16px;
  animation: rise 0.32s cubic-bezier(0.2, 0.7, 0.2, 1);
}

@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
}

.message-row.user {
  justify-content: flex-end;
}

.message-row.assistant {
  justify-content: flex-start;
}

.message-bubble {
  max-width: 85%;
  padding: 12px 16px;
  border-radius: 10px;
  font-size: 14px;
  line-height: 1.6;
}

.message-row.user .message-bubble {
  background: var(--brand);
  color: #fff;
  border-bottom-right-radius: 3px;
  box-shadow: 0 1px 2px rgba(37, 99, 235, 0.2);
}

.message-row.assistant .message-bubble {
  background: var(--surface);
  color: var(--ink);
  border: 1px solid var(--border);
  border-bottom-left-radius: 3px;
  box-shadow: var(--shadow-xs);
}

.loading-dots {
  display: flex;
  gap: 6px;
  padding: 4px 0;
}

.loading-dots span {
  width: 8px;
  height: 8px;
  background: var(--ink-4);
  border-radius: 50%;
  animation: bounce 1.2s infinite ease-in-out;
}

.loading-dots span:nth-child(2) {
  animation-delay: 0.2s;
}

.loading-dots span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes bounce {
  0%,
  80%,
  100% {
    transform: scale(0.6);
    opacity: 0.4;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

.result-summary {
  color: var(--ink-3);
  margin-bottom: 12px;
}

.result-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.result-card {
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-left: 3px solid var(--brand);
  border-radius: 8px;
  padding: 12px;
}

.result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.result-source {
  display: flex;
  gap: 6px;
}

.result-score {
  font-size: 12px;
  color: var(--success);
  font-weight: 600;
}

.result-heading {
  font-size: 12px;
  color: var(--ink-3);
  margin-bottom: 6px;
}

.result-content {
  font-size: 13px;
  line-height: 1.7;
  color: var(--ink-2);
}

.result-content :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 6px 0;
}

.result-content :deep(th),
.result-content :deep(td) {
  border: 1px solid var(--border-strong);
  padding: 4px 8px;
  font-size: 12px;
}

.result-content :deep(th) {
  background: var(--surface-3);
}

.result-content :deep(mark) {
  background: #fef08a;
  color: inherit;
  padding: 0 2px;
  border-radius: 2px;
}

.chat-input-area {
  padding: 12px 0 0;
  border-top: 1px solid var(--border);
}

.mode-bar {
  margin-bottom: 10px;
}

.input-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
}
</style>
