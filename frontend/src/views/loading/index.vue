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
      <article
        v-for="item in stats"
        :key="item.label"
        class="stat-card"
        :class="{ clickable: item.label === '缺班组任务', active: item.label === '缺班组任务' && abnormalOnly }"
        @click="toggleAbnormal(item)"
      >
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
      <span v-if="abnormalOnly" class="filter-hint">当前只看缺作业班组的任务，再次点击「缺班组任务」卡片可取消</span>
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
            {{ row[column] ?? '—' }}
            <span v-if="column === '作业班组' && !row[column]" class="tag-warn">缺班组</span>
          </td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(row)">详情</button>
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

    <footer class="page-foot">
      <span>共 {{ total }} 条装卸任务记录</span>
      <span v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { fetchJson, request } from '@/api/client'

type Row = Record<string, string | number | null>
type StatItem = { label: string; value: number }

const ENDPOINT = '/api/loading'
const columns = ["任务编号", "关联航次", "作业类型", "计划箱量", "完成箱量", "作业班组", "开始时间", "任务状态"]
const actions = ["确认开工", "提交复核", "确认完成"]
const statuses = ["待开工", "作业中", "待复核", "已完成"]

const router = useRouter()
const rows = ref<Row[]>([])
const stats = ref<StatItem[]>([])
const total = ref(0)
const abnormalOnly = ref(false)
const noticeMessage = ref('')
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

function resetFilters() {
  filters.value = {}
  abnormalOnly.value = false
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '装卸任务登记入口尚未接入审批流'
}

function openDetail(row: Row) {
  void router.push(`/loading/${row.id}`)
}

function toggleAbnormal(item: StatItem) {
  if (item.label !== '缺班组任务') return
  abnormalOnly.value = !abnormalOnly.value
  void reload()
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload?.message ?? payload?.detail ?? '装卸任务动作未生效，请稍后重试')
    }
    noticeMessage.value = payload.message || `装卸任务已${action}`
    await Promise.all([reload(), loadStats()])
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '装卸任务操作失败'
  }
}

async function loadStats() {
  try {
    const payload = await fetchJson<{ items: StatItem[] }>(`${ENDPOINT}/stats`)
    stats.value = payload.items ?? []
  } catch {
    stats.value = []
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>)
  if (abnormalOnly.value) {
    query.set('abnormal', 'true')
  }
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error('装卸任务列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '装卸任务列表读取失败'
  }
}

onMounted(() => {
  void reload()
  void loadStats()
})
</script>
