<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { CronExpressionParser } from 'cron-parser'
import { ElButton, ElInput, ElTable, ElTableColumn, ElForm, ElFormItem, ElDialog, ElMessage, ElTag, ElTooltip, ElIcon, ElPagination } from 'element-plus'
import { WarningFilled } from '@element-plus/icons-vue'

// API 基础 URL - 生产环境
const API_BASE_URL = 'http://120.79.224.20:8000'
// const API_BASE_URL = 'http://localhost:8000'  // 本地开发环境

// 模拟 API 调用
const api = {
  // 获取任务列表
  async getTasks() {
    try {
      const response = await fetch(`${API_BASE_URL}/tasks`)
      return await response.json()
    } catch (error) {
      console.error('获取任务列表失败:', error)
      return []
    }
  },
  
  // 添加任务
  async createTask(task) {
    try {
      const response = await fetch(`${API_BASE_URL}/tasks`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(task)
      })
      return await response.json()
    } catch (error) {
      console.error('添加任务失败:', error)
      throw error
    }
  },
  
  // 更新任务
  async updateTask(id, task) {
    try {
      const response = await fetch(`${API_BASE_URL}/tasks/${id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(task)
      })
      return await response.json()
    } catch (error) {
      console.error('更新任务失败:', error)
      throw error
    }
  },
  
  // 删除任务
  async deleteTask(id) {
    try {
      const response = await fetch(`${API_BASE_URL}/tasks/${id}`, {
        method: 'DELETE'
      })
      return await response.json()
    } catch (error) {
      console.error('删除任务失败:', error)
      throw error
    }
  },
  
  // 手动执行任务
  async executeTask(id) {
    try {
      const response = await fetch(`${API_BASE_URL}/tasks/${id}/execute`, {
        method: 'POST'
      })
      return await response.json()
    } catch (error) {
      console.error('执行任务失败:', error)
      throw error
    }
  },
  
  // 获取执行历史
  async getExecutionHistory() {
    try {
      const response = await fetch(`${API_BASE_URL}/execution-history`)
      return await response.json()
    } catch (error) {
      console.error('获取执行历史失败:', error)
      return []
    }
  },
  
  // 获取 Agent 列表
  async getAgents() {
    try {
      const response = await fetch(`${API_BASE_URL}/agents`)
      return await response.json()
    } catch (error) {
      console.error('获取Agent列表失败:', error)
      return []
    }
  },
  
  // 在 Agent 上执行任务
  async executeOnAgent(taskId, agentId) {
    try {
      const response = await fetch(`${API_BASE_URL}/tasks/${taskId}/execute-on-agent?agent_id=${agentId}`, {
        method: 'POST'
      })
      return await response.json()
    } catch (error) {
      console.error('在Agent上执行任务失败:', error)
      throw error
    }
  }
}

// 任务列表
const tasks = ref([])
// Agent 列表
const agents = ref([])
// 编辑对话框
const dialogVisible = ref(false)
// 任务表单
const taskForm = ref({
  id: '',
  name: '',
  cronExpression: '',
  description: '',
  cmd: '',
  timeout: 300,  // 默认超时时间 300 秒（5 分钟）
  agentId: ''  // 指定执行的 Agent ID
})
// 表单验证规则
const rules = {
  name: [{ required: true, message: '请输入任务名称', trigger: 'blur' }],
  cronExpression: [{ required: true, message: '请输入Cron表达式', trigger: 'blur' }],
  cmd: [{ required: true, message: '请输入CMD命令', trigger: 'blur' }]
}
// 编辑状态
const isEdit = ref(false)
// 执行历史
const executionHistory = ref([])
// 执行历史分页
const historyCurrentPage = ref(1)
const historyPageSize = ref(5)
// 任务状态
const taskStatus = ref({})

// 格式化日期为 yyyy-mm-dd HH:MM:SS
const formatDate = (date) => {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  const seconds = String(date.getSeconds()).padStart(2, '0')
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
}

// 执行历史分页数据
const paginatedHistory = computed(() => {
  const start = (historyCurrentPage.value - 1) * historyPageSize.value
  const end = start + historyPageSize.value
  return executionHistory.value.slice(start, end)
})

// 计算下一次执行时间
const getNextExecution = (cronExpr) => {
  try {
    // 去除 Cron 表达式中的首尾空格，并将多个连续空格替换为单个空格
    const cronExprTrimmed = cronExpr.trim().replace(/\s+/g, ' ')
    const interval = CronExpressionParser.parse(cronExprTrimmed)
    const nextDate = interval.next().toDate()
    return formatDate(nextDate)
  } catch (error) {
    console.error('解析Cron表达式失败:', error, '表达式:', cronExpr)
    return '无效的Cron表达式'
  }
}

// 计算后续执行时间列表
const getNextExecutions = (cronExpr, count = 5) => {
  try {
    // 去除 Cron 表达式中的首尾空格，并将多个连续空格替换为单个空格
    const cronExprTrimmed = cronExpr.trim().replace(/\s+/g, ' ')
    const interval = CronExpressionParser.parse(cronExprTrimmed)
    const executions = []
    for (let i = 0; i < count; i++) {
      executions.push(formatDate(interval.next().toDate()))
    }
    return executions
  } catch (error) {
    console.error('解析Cron表达式失败:', error, '表达式:', cronExpr)
    return []
  }
}

// 获取任务的最近执行记录
const getTaskRecentExecutions = (taskId, count = 5) => {
  return executionHistory.value
    .filter(h => h.taskId === taskId)
    .sort((a, b) => new Date(b.executionTime) - new Date(a.executionTime))
    .slice(0, count)
}

// 获取任务当前状态
const getTaskCurrentStatus = (taskId) => {
  const recentExecutions = getTaskRecentExecutions(taskId, 1)
  if (recentExecutions.length === 0) {
    return { text: '待执行', type: 'info' }
  }
  
  const latest = recentExecutions[0]
  if (latest.status === 'running') {
    return { text: '执行中', type: 'warning' }
  } else if (latest.status === 'success') {
    return { text: '成功', type: 'success' }
  } else {
    return { text: '失败', type: 'danger' }
  }
}

// 加载任务
const loadTasks = async () => {
  tasks.value = await api.getTasks()
}

// 加载 Agent 列表
const loadAgents = async () => {
  agents.value = await api.getAgents()
}

// 保存任务（不再需要，因为使用 API）
const saveTasks = () => {
  // 已移至 API 调用
}

// 打开添加任务对话框
const openAddDialog = () => {
  isEdit.value = false
  taskForm.value = {
    id: '',
    name: '',
    cronExpression: '',
    description: '',
    cmd: '',
    timeout: 300,  // 默认超时时间 300 秒（5 分钟）
    agentId: ''  // 默认不指定 Agent
  }
  dialogVisible.value = true
}

// 打开编辑任务对话框
const openEditDialog = (task) => {
  isEdit.value = true
  taskForm.value = { ...task }
  dialogVisible.value = true
}

// 保存任务
const saveTask = async () => {
  try {
    // 处理 Cron 表达式，去除首尾空格
    const taskData = {
      ...taskForm.value,
      cronExpression: taskForm.value.cronExpression.trim()
    }
    
    if (isEdit.value) {
      // 编辑任务
      await api.updateTask(taskData.id, taskData)
      ElMessage.success('任务更新成功')
    } else {
      // 添加任务
      await api.createTask(taskData)
      ElMessage.success('任务添加成功')
    }
    // 重新加载任务列表
    await loadTasks()
    dialogVisible.value = false
  } catch (error) {
    ElMessage.error(`保存任务失败: ${error.message}`)
  }
}

// 删除任务
const deleteTask = async (id) => {
  try {
    await api.deleteTask(id)
    // 重新加载任务列表
    await loadTasks()
    // 删除任务状态
    delete taskStatus.value[id]
    ElMessage.success('任务删除成功')
  } catch (error) {
    ElMessage.error(`删除任务失败: ${error.message}`)
  }
}

// 手动执行任务
const manualExecuteTask = async (task) => {
  try {
    const result = await api.executeTask(task.id)
    ElMessage.success(`任务 ${task.name} 已发送执行`)
    // 延迟刷新执行历史（等待 Agent 执行完成）
    setTimeout(async () => {
      await loadExecutionHistory()
      // 再次刷新确保获取最新结果
      setTimeout(async () => {
        await loadExecutionHistory()
      }, 3000)
    }, 2000)
  } catch (error) {
    ElMessage.error(`任务 ${task.name} 执行失败: ${error.message}`)
  }
}

// 加载执行历史
const loadExecutionHistory = async () => {
  executionHistory.value = await api.getExecutionHistory()
}

// 检查任务状态
const updateTaskStatus = () => {
  // 从执行历史中更新任务状态
  executionHistory.value.forEach(history => {
    if (!taskStatus.value[history.taskId] || new Date(history.executionTime) > new Date(taskStatus.value[history.taskId].lastExecution)) {
      taskStatus.value[history.taskId] = {
        lastExecution: history.executionTime,
        status: history.status
      }
    }
  })
}

// 组件挂载时加载任务和执行历史
onMounted(async () => {
  await loadTasks()
  await loadAgents()
  await loadExecutionHistory()
  updateTaskStatus()
  
  // 每30秒刷新一次任务列表和执行历史
  setInterval(async () => {
    await loadTasks()
    await loadAgents()
    await loadExecutionHistory()
    updateTaskStatus()
  }, 30000)
})

// 组件卸载时清理
onUnmounted(() => {
  // 清理逻辑
})
</script>

<template>
  <div class="container">
    <h1>RPA Scheduler</h1>
    
    <!-- Agent 管理区域 -->
    <div class="section">
      <h2>在线 Agent</h2>
      <el-table :data="agents" style="width: 100%" v-if="agents.length > 0">
        <el-table-column prop="agent_name" label="Agent 名称" width="180" />
        <el-table-column prop="hostname" label="主机名" width="150" />
        <el-table-column prop="platform" label="平台" width="100" />
        <el-table-column label="状态" width="80">
          <template #default>
            <el-tag type="success">在线</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="connected_at" label="连接时间" width="180">
          <template #default="{ row }">
            {{ formatDate(new Date(row.connected_at)) }}
          </template>
        </el-table-column>
        <el-table-column prop="last_ping" label="最后心跳" width="180">
          <template #default="{ row }">
            {{ formatDate(new Date(row.last_ping)) }}
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="暂无在线 Agent" />
    </div>
    
    <div class="actions">
      <el-button type="primary" @click="openAddDialog">添加任务</el-button>
    </div>
    
    <el-table :data="tasks" style="width: 100%">
      <el-table-column label="任务名称" min-width="140" show-overflow-tooltip>
        <template #default="{ row }">
          <el-tooltip :content="row.name" placement="top" :disabled="row.name.length <= 20">
            <span class="ellipsis-text">{{ row.name }}</span>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column label="执行Agent" min-width="120">
        <template #default="{ row }">
          <el-tooltip v-if="row.agentId" :content="agents.find(a => a.agent_id === row.agentId)?.agent_name || row.agentId" placement="top">
            <span class="ellipsis-text">{{ agents.find(a => a.agent_id === row.agentId)?.agent_name || row.agentId }}</span>
          </el-tooltip>
          <span v-else style="color: #999;">本地执行</span>
        </template>
      </el-table-column>
      <el-table-column label="Cron表达式" width="140">
        <template #header>
          <span>
            Cron表达式
            <el-tooltip content="Cron表达式格式: 分 时 日 月 周\n示例:\n- 0 0 * * * 每天午夜执行\n- 0 */2 * * * 每2小时执行\n- 0 9-17 * * 1-5 工作日9-17点每小时执行" placement="top">
              <span class="cron-tip">
                <el-icon style="font-size: 16px; color: #f7ba2a;">
                  <WarningFilled />
                </el-icon>
              </span>
            </el-tooltip>
          </span>
        </template>
        <template #default="{ row }">
          <span style="display: flex; align-items: center;">
            {{ row.cronExpression }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="下一次执行" width="150">
        <template #default="{ row }">
          {{ getNextExecution(row.cronExpression) }}
        </template>
      </el-table-column>
      <el-table-column label="最近5次执行" width="100">
        <template #default="{ row }">
          <el-tooltip placement="top">
            <template #content>
              <div v-for="(exec, index) in getTaskRecentExecutions(row.id, 5)" :key="index" style="margin: 4px 0;">
                <span :style="{ color: exec.status === 'success' ? '#67c23a' : exec.status === 'running' ? '#e6a23c' : '#f56c6c' }">
                  {{ exec.status === 'success' ? '✓' : exec.status === 'running' ? '◐' : '✗' }}
                </span>
                {{ formatDate(new Date(exec.executionTime)) }}
                <span v-if="exec.duration" style="color: #909399; margin-left: 8px;">({{ exec.duration }})</span>
              </div>
              <div v-if="getTaskRecentExecutions(row.id, 5).length === 0" style="color: #909399;">暂无执行记录</div>
            </template>
            <div class="recent-executions">
              <div v-for="(exec, index) in getTaskRecentExecutions(row.id, 5).slice(0, 2)" :key="index" class="execution-item">
                <el-tag 
                  :type="exec.status === 'success' ? 'success' : exec.status === 'running' ? 'warning' : 'danger'" 
                  size="small" 
                  class="execution-tag"
                >
                  {{ exec.status === 'success' ? '✓' : exec.status === 'running' ? '◐' : '✗' }}
                </el-tag>
                <span class="execution-time">{{ formatDate(new Date(exec.executionTime)) }}</span>
              </div>
              <span v-if="getTaskRecentExecutions(row.id, 5).length === 0" style="color: #999; font-size: 12px;">暂无执行记录</span>
              <span v-else-if="getTaskRecentExecutions(row.id, 5).length > 2" style="color: #409eff; font-size: 12px; cursor: pointer;">+{{ getTaskRecentExecutions(row.id, 5).length - 2 }}条</span>
            </div>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="getTaskCurrentStatus(row.id).type">
            {{ getTaskCurrentStatus(row.id).text }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="CMD命令" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">
          <el-tooltip :content="row.cmd" placement="top" :disabled="row.cmd.length <= 30">
            <span class="ellipsis-text">{{ row.cmd }}</span>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column label="超时时间" width="80">
        <template #default="{ row }">
          {{ row.timeout || 300 }}s
        </template>
      </el-table-column>
      <el-table-column label="描述" min-width="150" show-overflow-tooltip>
        <template #default="{ row }">
          <el-tooltip :content="row.description" placement="top" :disabled="!row.description || row.description.length <= 15">
            <span class="ellipsis-text">{{ row.description || '-' }}</span>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="manualExecuteTask(row)">执行</el-button>
          <el-button size="small" @click="openEditDialog(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="deleteTask(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    
    <h2>执行历史</h2>
    <el-table :data="paginatedHistory" style="width: 100%">
      <el-table-column prop="taskName" label="任务名称" width="160" />
      <el-table-column label="执行Agent" width="150">
        <template #default="{ row }">
          <el-tooltip v-if="row.agentId" :content="agents.find(a => a.agent_id === row.agentId)?.agent_name || row.agentId" placement="top">
            <span class="ellipsis-text">{{ agents.find(a => a.agent_id === row.agentId)?.agent_name || row.agentId }}</span>
          </el-tooltip>
          <span v-else style="color: #999;">本地执行</span>
        </template>
      </el-table-column>
      <el-table-column label="CMD命令" width="250" show-overflow-tooltip>
        <template #default="{ row }">
          <el-tooltip :content="row.cmd" placement="top" :disabled="!row.cmd || row.cmd.length <= 30">
            <span class="ellipsis-text">{{ row.cmd }}</span>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column prop="executionTime" label="执行时间" width="180">
        <template #default="{ row }">
          {{ formatDate(new Date(row.executionTime)) }}
        </template>
      </el-table-column>
      <el-table-column prop="duration" label="执行时长" width="120">
        <template #default="{ row }">
          <el-tag v-if="row.duration" type="info" size="small">
            {{ row.duration }}
          </el-tag>
          <span v-else style="color: #999;">-</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'success' ? 'success' : row.status === 'running' ? 'warning' : 'danger'">
            {{ row.status === 'success' ? '成功' : row.status === 'running' ? '执行中' : '失败' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="output" label="输出" />
    </el-table>
    <el-pagination
      v-model:current-page="historyCurrentPage"
      v-model:page-size="historyPageSize"
      :page-sizes="[5, 10, 20, 50]"
      :total="executionHistory.length"
      layout="total, sizes, prev, pager, next"
      style="margin-top: 20px; justify-content: center;"
    />
    
    <el-dialog
      :title="isEdit ? '编辑任务' : '添加任务'"
      v-model="dialogVisible"
      width="500px"
    >
      <el-form :model="taskForm" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="任务名称" prop="name">
          <el-input v-model="taskForm.name" placeholder="请输入任务名称" />
        </el-form-item>
        <el-form-item label="Cron表达式" prop="cronExpression">
          <el-input v-model="taskForm.cronExpression" placeholder="请输入Cron表达式" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="taskForm.description" type="textarea" placeholder="请输入任务描述" />
        </el-form-item>
        <el-form-item label="CMD命令" prop="cmd">
          <el-input v-model="taskForm.cmd" type="textarea" placeholder="请输入CMD命令" rows="3" />
        </el-form-item>
        <el-form-item label="超时时间">
          <el-input-number v-model="taskForm.timeout" :min="1" :max="86400" placeholder="秒" />
          <span style="margin-left: 8px; color: #666;">秒（默认 300 秒 = 5 分钟，最大 86400 秒 = 24 小时）</span>
        </el-form-item>
        <el-form-item label="执行Agent">
          <el-select v-model="taskForm.agentId" placeholder="请选择执行任务的Agent（可选）" clearable style="width: 100%">
            <el-option
              v-for="agent in agents"
              :key="agent.agent_id"
              :label="`${agent.agent_name} (${agent.hostname})`"
              :value="agent.agent_id"
            />
          </el-select>
          <div style="margin-top: 4px; color: #999; font-size: 12px;">
            不选择则在服务器本地执行
          </div>
        </el-form-item>
        <el-form-item v-if="taskForm.cronExpression">
          <label>后续执行时间：</label>
          <div class="execution-times">
            <el-tag v-for="(time, index) in getNextExecutions(taskForm.cronExpression)" :key="index" size="small" class="time-tag">
              {{ time }}
            </el-tag>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="saveTask">确定</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.container {
  max-width: 95%;
  margin: 0 auto;
  padding: 20px;
}

h1 {
  text-align: center;
  margin-bottom: 30px;
  color: #333;
}

.actions {
  margin-bottom: 20px;
}

.execution-times {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.time-tag {
  margin-bottom: 5px;
}

.dialog-footer {
  text-align: right;
}

.cron-tip {
  margin-left: 5px;
  cursor: pointer;
  vertical-align: middle;
  display: inline-block;
  margin-top: -2px;
}

.ellipsis-text {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: block;
  max-width: 100%;
}

.recent-executions {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.execution-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}

.execution-tag {
  min-width: 24px;
  text-align: center;
  padding: 0 4px;
}

.execution-time {
  color: #666;
  font-family: monospace;
}
</style>
