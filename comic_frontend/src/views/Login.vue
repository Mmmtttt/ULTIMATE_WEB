<template>
  <div class="login-page">
    <div class="login-container">
      <div class="login-header">
        <h1>Ultimate Web</h1>
        <p class="subtitle">请输入访问密码</p>
      </div>

      <form class="login-form" @submit.prevent="handleLogin">
        <div class="form-group">
          <input
            ref="passwordInput"
            v-model="password"
            type="password"
            class="password-input"
            placeholder="请输入密码"
            :disabled="loading"
            autocomplete="current-password"
          />
        </div>

        <button type="submit" class="login-btn" :disabled="loading || !password">
          <span v-if="loading">登录中...</span>
          <span v-else>进入</span>
        </button>
      </form>

      <div class="login-footer">
        <p>欢迎使用 Ultimate Web</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const password = ref('')
const loading = ref(false)
const passwordInput = ref(null)

onMounted(() => {
  nextTick(() => {
    passwordInput.value?.focus()
  })
})

async function handleLogin() {
  if (!password.value || loading.value) return

  loading.value = true

  try {
    // 无论密码正确与否，都进入应用
    // 正确 → normal 模式，错误 → private 模式（隐私保护）
    await authStore.login(password.value)

    const redirect = route.query.redirect || '/library'
    router.replace(redirect)
  } catch (e) {
    // 网络错误等异常情况也直接进入隐私模式
    authStore.switchToPrivateMode()
    const redirect = route.query.redirect || '/library'
    router.replace(redirect)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
}

.login-container {
  width: 100%;
  max-width: 400px;
  background: #fff;
  border-radius: 16px;
  padding: 48px 40px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.login-header {
  text-align: center;
  margin-bottom: 36px;
}

.login-header h1 {
  font-size: 28px;
  font-weight: 700;
  color: #1a1a2e;
  margin: 0 0 8px 0;
}

.subtitle {
  font-size: 14px;
  color: #888;
  margin: 0;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-group {
  display: flex;
  flex-direction: column;
}

.password-input {
  width: 100%;
  height: 48px;
  padding: 0 16px;
  font-size: 16px;
  border: 2px solid #e0e0e0;
  border-radius: 10px;
  outline: none;
  transition: border-color 0.2s;
  box-sizing: border-box;
}

.password-input:focus {
  border-color: #667eea;
}

.password-input:disabled {
  background: #f5f5f5;
  cursor: not-allowed;
}

.login-btn {
  width: 100%;
  height: 48px;
  font-size: 16px;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  border-radius: 10px;
  cursor: pointer;
  transition: opacity 0.2s, transform 0.1s;
}

.login-btn:hover:not(:disabled) {
  opacity: 0.9;
}

.login-btn:active:not(:disabled) {
  transform: scale(0.98);
}

.login-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.error-tip {
  color: #e74c3c;
  font-size: 13px;
  margin: 0;
  text-align: center;
}

.login-footer {
  margin-top: 24px;
  text-align: center;
}

.login-footer p {
  font-size: 12px;
  color: #aaa;
  margin: 0;
}
</style>
