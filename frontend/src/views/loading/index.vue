<template>
  <section class="page" data-module="loading">
    <header class="page-head">
      <div>
        <h2>装卸任务管理</h2>
        <p class="page-desc">维护装卸任务，围绕任务编号、关联航次、作业类型、计划箱量做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记装卸任务</button>
        <button class="btn" type="button" @click="exportRows">导出装卸任务清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>任务编号</span>
        <input v-model="filters.keyword" placeholder="按任务编号检索" />
      </label>
      <label class="filter-item">
        <span>任务状态</span>
        <select v-model="filters.status">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <label class="filter-item checkbox-item">
        <input v-model="filters.missingGang" type="checkbox" />
        <span>只看班组缺失</span>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">
            <span v-if="column === '作业班组' && isMissingGang(row)" class="warn-text">未安排</span>
            <template v-else>{{ row[column] ?? '—' }}</template>
          </td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(row)">查看</button>
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无装卸任务数据，可先登记装卸任务</td>
        </tr>
      </tbody>
    </table>

    <aside v-if="detail" class="detail-panel">
      <header class="detail-head">
        <h3>装卸任务详情 · {{ detail['任务编号'] }}</h3>
        <button class="link" type="button" @click="closeDetail">关闭</button>
      </header>
      <dl class="detail-grid">
        <template v-for="column in columns" :key="column">
          <dt>{{ column }}</dt>
          <dd v-if="column === '完成箱量'">
            <input v-model="detailForm.完成箱量" inputmode="numeric" placeholder="提交完成箱量" />
          </dd>
          <dd v-else-if="column === '作业班组'">
            <input v-model="detailForm.作业班组" placeholder="未安排班组" />
          </dd>
          <dd v-else>{{ detail[column] ?? '—' }}</dd>
        </template>
      </dl>
      <p v-if="isMissingGang(detail)" class="warn-text">该任务尚未安排作业班组，请先在详情里补齐。</p>
      <div class="row-actions detail-actions">
        <button
          v-for="action in actions"
          :key="action"
          class="btn"
          type="button"
          @click="runAction(action, detail, true)"
        >
          {{ action }}
        </button>
      </div>
    </aside>

    <footer class="page-foot">
      <span>共 {{ total }} 条装卸任务记录</span>
      <span v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { fetchJson, request } from '@/api/client'

type Row = Record<string, any>

const ENDPOINT = '/api/loading'
const columns = ["任务编号", "关联航次", "作业类型", "计划箱量", "完成箱量", "作业班组", "开始时间", "任务状态"]
const actions = ["确认开工", "提交复核", "确认完成"]
const statuses = ["待开工", "作业中", "待复核", "已完成"]

const rows = ref<Row[]>([])
const total = ref(0)
const stats = ref([
  { label: '待开工任务', value: 0 },
  { label: '作业中任务', value: 0 },
  { label: '今日完成箱量', value: 0 },
  { label: '班组缺失任务', value: 0 },
])
const filters = ref({ keyword: '', status: '', missingGang: false })
const detail = ref<Row | null>(null)
const detailForm = ref({ 完成箱量: '', 作业班组: '' })
const noticeMessage = ref('')
const errorMessage = ref('')

function isMissingGang(row: Row) {
  return !String(row['作业班组'] ?? '').trim()
}

function resetFilters() {
  filters.value = { keyword: '', status: '', missingGang: false }
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '装卸任务登记入口尚未接入审批流'
}

function syncDetailForm(entry: Row) {
  detailForm.value = {
    完成箱量: String(entry['完成箱量'] ?? ''),
    作业班组: String(entry['作业班组'] ?? ''),
  }
}

async function openDetail(row: Row) {
  errorMessage.value = ''
  try {
    const entry = await fetchJson<Row>(`${ENDPOINT}/${row.id}`)
    detail.value = entry
    syncDetailForm(entry)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '装卸任务详情读取失败'
  }
}

function closeDetail() {
  detail.value = null
}

async function runAction(action: string, row: Row, withDetailValues = false) {
  errorMessage.value = ''
  noticeMessage.value = ''
  const values: Record<string, unknown> = { action }
  if (withDetailValues) {
    values['完成箱量'] = detailForm.value.完成箱量
    values['作业班组'] = detailForm.value.作业班组
  }
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload?.message ?? payload?.detail ?? '装卸任务动作未生效，请稍后重试')
    }
    noticeMessage.value = payload.message ?? `装卸任务已${action}`
    if (payload.entry) {
      patchRow(payload.entry)
      if (detail.value?.id === payload.entry.id) {
        detail.value = payload.entry
        syncDetailForm(payload.entry)
      }
    }
    await Promise.all([reload(), loadSummary()])
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '装卸任务操作失败'
  }
}

function patchRow(entry: Row) {
  const index = rows.value.findIndex((row) => row.id === entry.id)
  if (index >= 0) {
    rows.value[index] = entry
  }
}

async function reload() {
  const query = new URLSearchParams()
  if (filters.value.keyword.trim()) query.set('keyword', filters.value.keyword.trim())
  if (filters.value.status) query.set('status', filters.value.status)
  if (filters.value.missingGang) query.set('missing_gang', 'true')
  try {
    const payload = await fetchJson<{ items: Row[]; total: number }>(`${ENDPOINT}?${query}`)
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '装卸任务列表读取失败'
  }
}

async function loadSummary() {
  try {
    const payload = await fetchJson<{
      status_counts: Record<string, number>
      completed_quantity: number
      missing_gang: number
    }>(`${ENDPOINT}/summary`)
    stats.value = [
      { label: '待开工任务', value: payload.status_counts?.['待开工'] ?? 0 },
      { label: '作业中任务', value: payload.status_counts?.['作业中'] ?? 0 },
      { label: '今日完成箱量', value: payload.completed_quantity ?? 0 },
      { label: '班组缺失任务', value: payload.missing_gang ?? 0 },
    ]
  } catch {
    // 看板读取失败不挡列表，卡片保持上一次的结果
  }
}

onMounted(() => {
  void reload()
  void loadSummary()
})
</script>

<style scoped>
.checkbox-item {
  display: flex;
  align-items: center;
  gap: 4px;
}
.detail-panel {
  margin-top: 12px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px 16px;
}
.detail-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.detail-head h3 {
  margin: 0;
  font-size: 15px;
}
.detail-grid {
  display: grid;
  grid-template-columns: 96px 1fr 96px 1fr;
  gap: 8px 12px;
  margin: 12px 0;
  font-size: 13px;
}
.detail-grid dt {
  color: var(--muted);
}
.detail-grid dd {
  margin: 0;
}
.detail-grid input {
  width: 180px;
}
.detail-actions {
  margin-top: 4px;
}
.warn-text {
  color: #b42318;
}
.notice-text {
  color: #067647;
}
</style>
