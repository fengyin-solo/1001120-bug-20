<template>
  <section class="page" data-module="loading-detail">
    <header class="page-head">
      <div>
        <h2>装卸任务详情</h2>
        <p class="page-desc">任务编号 {{ entry?.['任务编号'] ?? entryId }}，状态与完成箱量以服务端记录为准。</p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="goBack">返回列表</button>
      </div>
    </header>

    <table v-if="entry" class="data-table detail-table">
      <tbody>
        <tr v-for="field in fields" :key="field">
          <th>{{ field }}</th>
          <td>
            {{ entry[field] ?? '—' }}
            <span v-if="field === '作业班组' && !entry[field]" class="tag-warn">缺班组</span>
          </td>
        </tr>
      </tbody>
    </table>

    <template v-if="entry">
      <form class="filter-bar" @submit.prevent>
        <label class="filter-item">
          <span>完成箱量</span>
          <input v-model="form.完成箱量" type="number" min="0" placeholder="提交复核时写入" />
        </label>
        <label class="filter-item">
          <span>作业班组</span>
          <input v-model="form.作业班组" placeholder="补齐作业班组后随动作提交" />
        </label>
      </form>
      <div class="detail-actions">
        <button
          v-for="action in actions"
          :key="action"
          class="btn primary"
          type="button"
          @click="runAction(action)"
        >
          {{ action }}
        </button>
      </div>
    </template>

    <footer class="page-foot">
      <span v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { fetchJson, request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/loading'
const fields = ["任务编号", "关联航次", "作业类型", "计划箱量", "完成箱量", "作业班组", "开始时间", "完成时间", "任务状态"]
const actions = ["确认开工", "提交复核", "确认完成"]

const route = useRoute()
const router = useRouter()
const entryId = String(route.params.id)
const entry = ref<Row | null>(null)
const form = ref({ 完成箱量: '', 作业班组: '' })
const noticeMessage = ref('')
const errorMessage = ref('')

function goBack() {
  void router.push('/loading')
}

function syncForm(source: Row) {
  form.value = {
    完成箱量: source['完成箱量'] != null ? String(source['完成箱量']) : '',
    作业班组: source['作业班组'] != null ? String(source['作业班组']) : '',
  }
}

async function load() {
  errorMessage.value = ''
  try {
    const payload = await fetchJson<Row>(`${ENDPOINT}/${entryId}`)
    entry.value = payload
    syncForm(payload)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '装卸任务详情读取失败'
  }
}

async function runAction(action: string) {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${entryId}/actions`, {
      method: 'POST',
      body: JSON.stringify({
        action,
        完成箱量: form.value.完成箱量,
        作业班组: form.value.作业班组,
      }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload?.message ?? payload?.detail ?? '装卸任务动作未生效，请稍后重试')
    }
    if (payload.entry) {
      entry.value = payload.entry
      syncForm(payload.entry)
    }
    noticeMessage.value = payload.message || `装卸任务已${action}`
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '装卸任务操作失败'
  }
}

onMounted(load)
</script>
