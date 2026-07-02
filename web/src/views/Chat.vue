<script setup lang="ts">
import { ref, nextTick, computed } from 'vue'
import { Promotion, UserFilled, Cpu, Search } from '@element-plus/icons-vue'
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

const modeLabel: Record<string, string> = { bm25: 'BM25', vector: '向量', hybrid: '混合' }

const modeOptions = [
  { label: '混合', value: 'hybrid' as const },
  { label: 'BM25', value: 'bm25' as const },
  { label: '向量', value: 'vector' as const },
]

const messages = computed(() => chatStore.messages)
const canSend = computed(() => inputQuery.value.trim() && !messages.value.some((m) => m.loading))

function renderMarkdown(text: string): string {
  return md.render(text)
}

/** 将 [1] [2,3] 引用转为可点击链接 */
function renderCitations(text: string, msgIdx: number): string {
  return text.replace(
    /\[(\d+(?:,\d+)*)\]/g,
    (_, nums: string) => {
      const ids = nums.split(',').map((n: string) => n.trim())
      return ids.map((id: string) =>
        `<a class="cite-link" href="#" data-ref="${msgIdx}-${id}">[${id}]</a>`
      ).join('')
    }
  )
}

/** 委托点击：引用链接滚动到对应卡片 */
function handleCiteClick(e: Event) {
  const target = e.target as HTMLElement
  if (!target.classList.contains('cite-link')) return
  e.preventDefault()
  const ref = target.dataset.ref
  if (!ref) return
  const card = document.getElementById(`card-${ref}`)
  if (card) {
    card.scrollIntoView({ behavior: 'smooth', block: 'center' })
    card.classList.add('highlight')
    setTimeout(() => card.classList.remove('highlight'), 2000)
  }
}

function formatScore(score: number): string {
  return (score * 100).toFixed(0) + '%'
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
    <!-- 消息区 -->
    <div ref="chatContainer" class="chat-messages" @click="handleCiteClick">
      <!-- 空状态 -->
      <div v-if="messages.length === 0" class="empty-state">
        <div class="empty-icon-wrap">
          <Search :size="32" />
        </div>
        <h2 class="empty-title">检索知识库</h2>
        <p class="empty-tip">输入问题，从文档中找到最相关的片段</p>
        <div class="empty-suggestions">
          <button
            v-for="q in ['电气工程自动化的发展趋势', '什么是人工智能', 'RAG 系统的架构设计']"
            :key="q"
            class="sug-btn"
            @click="inputQuery = q; sendQuery()"
          >{{ q }}</button>
        </div>
      </div>

      <!-- 消息列表 -->
      <div v-for="(msg, i) in messages" :key="i" :class="['message-row', msg.role]">
        <div class="message-avatar">
          <span v-if="msg.role === 'user'" class="avatar user-avatar"><UserFilled /></span>
          <span v-else class="avatar bot-avatar"><Cpu /></span>
        </div>

        <div class="message-body">
          <div v-if="msg.role === 'user'" class="user-bubble">{{ msg.content }}</div>

          <div v-else class="bot-bubble">
            <div v-if="msg.loading" class="loading-state">
              <span class="typing-dots"><i></i><i></i><i></i></span>
              <span class="loading-text">检索中</span>
            </div>

            <template v-else>
              <div class="meta-line">
                <span v-if="msg.mode" class="mode-badge">{{ modeLabel[msg.mode] }}</span>
                <span>{{ msg.content }}</span>
              </div>

              <div v-if="msg.answer" class="llm-answer">
                <div class="llm-answer-label">AI 总结</div>
                <div class="llm-answer-content" v-html="renderCitations(renderMarkdown(msg.answer), i)"></div>
              </div>

              <div v-if="msg.results?.length" class="results-grid">
                <div v-for="(r, ri) in msg.results" :key="ri" :id="`card-${i}-${ri + 1}`" class="result-card">
                  <div class="card-top">
                    <span class="cite-num">{{ ri + 1 }}</span>
                    <div class="card-meta">
                      <span class="card-file" :title="r.file_name">{{ r.file_name }}</span>
                      <span v-if="r.page_numbers?.length" class="card-page">P{{ r.page_numbers[0] }}</span>
                      <span v-if="r.heading_context && r.heading_context !== 'Root'" class="card-heading">{{ r.heading_context }}</span>
                    </div>
                    <span :class="['card-score', { 'bm25-rank': msg.mode === 'bm25' }]">
                      {{ msg.mode === 'bm25' ? '#' + (ri + 1) : formatScore(r.score) }}
                    </span>
                  </div>
                  <div
                    class="card-content"
                    v-html="msg.mode === 'bm25' && msg.tokens
                      ? highlightTokens(r.content, msg.tokens)
                      : renderMarkdown(r.content)"
                  ></div>
                </div>
              </div>

              <div v-else class="no-results">未找到相关内容，试试换个问法或切换检索模式</div>
            </template>
          </div>
        </div>
      </div>
    </div>

    <!-- 底部控制栏 -->
    <div class="chat-footer">
      <div class="toolbar">
        <div class="toolbar-left">
          <div class="mode-toggle">
            <button
              v-for="m in modeOptions"
              :key="m.value"
              :class="['mode-chip', { active: chatStore.mode === m.value }]"
              @click="chatStore.mode = m.value"
            >{{ m.label }}</button>
          </div>

          <label class="llm-toggle" title="启用 LLM 总结答案">
            <input type="checkbox" v-model="chatStore.useLLM" />
            <span class="llm-label">AI 总结</span>
          </label>
        </div>

        <button class="clear-btn" @click="clearChat" :disabled="messages.length === 0">清空</button>
      </div>

      <div class="input-wrap">
        <textarea
          v-model="inputQuery"
          class="query-input"
          placeholder="输入问题，Enter 发送"
          rows="1"
          @keydown="handleKeydown"
          :disabled="messages.some((m) => m.loading)"
        ></textarea>
        <button class="send-btn" :disabled="!canSend" @click="sendQuery">
          <el-icon :size="18"><Promotion /></el-icon>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ========== Layout ========== */
.chat-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 60px - 40px);
  max-width: 820px;
  margin: 0 auto;
  width: 100%;
  background: var(--surface);
}

/* ========== Messages ========== */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0 16px;
  scroll-behavior: smooth;
}

/* Empty */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
}

.empty-icon-wrap {
  width: 64px;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 16px;
  background: var(--brand-soft);
  color: var(--brand);
  margin-bottom: 18px;
}

.empty-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--ink-1);
  margin: 0 0 6px;
}

.empty-tip {
  font-size: 14px;
  color: var(--ink-4);
  margin: 0 0 22px;
}

.empty-suggestions {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 300px;
}

.sug-btn {
  font-size: 13px;
  padding: 8px 16px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface);
  color: var(--ink-2);
  cursor: pointer;
  transition: all 0.15s;
  text-align: left;
}

.sug-btn:hover {
  border-color: var(--brand);
  color: var(--brand);
  background: var(--brand-soft);
}

/* Message row */
.message-row {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
  animation: rise 0.3s cubic-bezier(0.2, 0.7, 0.2, 1);
}

@keyframes rise {
  from { opacity: 0; transform: translateY(8px); }
}

.message-row.user { flex-direction: row-reverse; }

.message-avatar {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
}

.avatar {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
}

.user-avatar { background: var(--brand); color: #fff; }
.bot-avatar { background: var(--surface-2); color: var(--brand); border: 1px solid var(--border); }

.message-body { max-width: 80%; min-width: 0; }

.user-bubble {
  background: var(--brand);
  color: #fff;
  padding: 10px 16px;
  border-radius: 12px 12px 4px 12px;
  font-size: 14px;
  line-height: 1.55;
  box-shadow: 0 2px 6px rgba(37, 99, 235, 0.15);
}

.bot-bubble { font-size: 14px; line-height: 1.55; }

/* Loading */
.loading-state {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  color: var(--ink-4);
  font-size: 13px;
}

.typing-dots { display: flex; gap: 3px; align-items: center; }
.typing-dots i {
  width: 5px; height: 5px; border-radius: 50%;
  background: var(--ink-4);
  animation: bounce 1.4s infinite ease-in-out;
}
.typing-dots i:nth-child(2) { animation-delay: 0.2s; }
.typing-dots i:nth-child(3) { animation-delay: 0.4s; }

@keyframes bounce {
  0%, 80%, 100% { transform: translateY(0); opacity: 0.3; }
  40% { transform: translateY(-5px); opacity: 1; }
}

.meta-line {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--ink-3);
  font-size: 13px;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
}

/* LLM answer */
.llm-answer {
  background: linear-gradient(135deg, var(--brand-soft), transparent);
  border: 1px solid var(--brand);
  border-radius: 10px;
  padding: 14px;
  margin-bottom: 14px;
}

.llm-answer-label {
  font-size: 11px;
  font-weight: 700;
  color: var(--brand);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}

.llm-answer-content {
  font-size: 14px;
  line-height: 1.7;
  color: var(--ink-1);
}

.llm-answer-content :deep(.cite-link) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 4px;
  border-radius: 4px;
  background: var(--brand-soft);
  color: var(--brand);
  font-size: 11px;
  font-weight: 700;
  text-decoration: none;
  vertical-align: middle;
  margin: 0 1px;
  transition: background 0.15s;
}

.llm-answer-content :deep(.cite-link:hover) {
  background: var(--brand);
  color: #fff;
}

.result-card.highlight {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px var(--brand-soft);
  transition: box-shadow 0.3s, border-color 0.3s;
}

.mode-badge {
  display: inline-block;
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--brand-soft);
  color: var(--brand);
  flex-shrink: 0;
}

/* Results */
.results-grid { display: flex; flex-direction: column; gap: 10px; }

.result-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
  transition: border-color 0.15s;
}
.result-card:hover { border-color: var(--brand); }

.card-top {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px 0;
}

.cite-num {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--brand);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
}

.card-meta { display: flex; flex-wrap: wrap; gap: 5px; font-size: 12px; min-width: 0; }

.card-file {
  font-weight: 600;
  color: var(--ink-1);
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-page {
  background: var(--surface-2);
  padding: 1px 6px;
  border-radius: 4px;
  color: var(--ink-3);
  font-size: 11px;
}

.card-heading {
  background: var(--brand-soft);
  color: var(--brand);
  padding: 1px 8px;
  border-radius: 4px;
  font-size: 11px;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-score {
  font-size: 12px;
  font-weight: 700;
  color: var(--success);
  flex-shrink: 0;
}

.card-score.bm25-rank {
  color: var(--ink-4);
  font-size: 11px;
  background: var(--surface-2);
  padding: 2px 8px;
  border-radius: 4px;
}

.card-content {
  padding: 8px 14px 12px;
  font-size: 13px;
  line-height: 1.75;
  color: var(--ink-2);
}

.card-content :deep(mark) {
  background: #fef08a;
  color: inherit;
  padding: 0 2px;
  border-radius: 2px;
}

.card-content :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 6px 0;
}

.card-content :deep(th),
.card-content :deep(td) {
  border: 1px solid var(--border);
  padding: 3px 7px;
  font-size: 12px;
}

.card-content :deep(th) { background: var(--surface-3); }

.no-results {
  color: var(--ink-4);
  font-size: 13px;
  text-align: center;
  padding: 16px;
}

/* ========== Footer ========== */
.chat-footer { flex-shrink: 0; padding: 8px 0 4px; }

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* Mode chips */
.mode-toggle {
  display: flex;
  gap: 3px;
  background: var(--surface-2);
  border-radius: 8px;
  padding: 2px;
}

.mode-chip {
  padding: 4px 10px;
  border: none;
  background: transparent;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  color: var(--ink-3);
  cursor: pointer;
  transition: all 0.15s;
}

.mode-chip:hover { color: var(--ink-1); }

.mode-chip.active {
  background: var(--brand);
  color: #fff;
}

/* LLM toggle */
.llm-toggle {
  display: flex;
  align-items: center;
  gap: 5px;
  cursor: pointer;
  font-size: 12px;
  color: var(--ink-3);
  user-select: none;
}

.llm-toggle input {
  width: 32px;
  height: 18px;
  appearance: none;
  background: var(--border);
  border-radius: 10px;
  position: relative;
  cursor: pointer;
  transition: background 0.2s;
}

.llm-toggle input::after {
  content: '';
  position: absolute;
  top: 2px;
  left: 2px;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #fff;
  transition: transform 0.2s;
}

.llm-toggle input:checked {
  background: var(--brand);
}

.llm-toggle input:checked::after {
  transform: translateX(14px);
}

.llm-label { transition: color 0.2s; }

.llm-toggle input:checked + .llm-label {
  color: var(--brand);
  font-weight: 600;
}

.clear-btn {
  font-size: 12px;
  color: var(--ink-4);
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px 6px;
  border-radius: 6px;
  transition: all 0.15s;
}
.clear-btn:hover:not(:disabled) { color: var(--ink-1); background: var(--surface-2); }
.clear-btn:disabled { opacity: 0.3; cursor: default; }

/* Input */
.input-wrap {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 8px 10px 8px 16px;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.input-wrap:focus-within {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px var(--brand-soft);
}

.query-input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 14px;
  line-height: 1.5;
  resize: none;
  font-family: inherit;
  color: var(--ink-1);
  max-height: 120px;
}
.query-input::placeholder { color: var(--ink-4); }
.query-input:disabled { opacity: 0.5; }

.send-btn {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  border: none;
  background: var(--brand);
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}
.send-btn:hover:not(:disabled) { background: #2563eb; transform: scale(1.05); }
.send-btn:disabled { opacity: 0.35; cursor: default; }
</style>
