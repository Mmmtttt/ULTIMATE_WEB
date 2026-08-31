<template>
  <div class="login-page">
    <div class="login-orb orb-a" aria-hidden="true"></div>
    <div class="login-orb orb-b" aria-hidden="true"></div>
    <div class="login-container">
      <div class="login-header">
        <div class="brand-mark">U</div>
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
  min-height: 100dvh;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  padding: calc(24px + env(safe-area-inset-top, 0px)) 18px calc(24px + env(safe-area-inset-bottom, 0px));
  background:
    radial-gradient(circle at 18% 18%, rgba(89, 160, 255, 0.26), transparent 30%),
    radial-gradient(circle at 82% 72%, rgba(0, 168, 117, 0.18), transparent 32%),
    linear-gradient(155deg, #07101f 0%, #101b31 48%, #081222 100%);
  color: #eef5ff;
}

.login-page::before {
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0.2;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.08) 1px, transparent 1px);
  background-size: 42px 42px;
  mask-image: radial-gradient(circle at center, #000, transparent 72%);
}

.login-orb {
  position: absolute;
  border-radius: 999px;
  filter: blur(2px);
  pointer-events: none;
}

.orb-a {
  width: 260px;
  height: 260px;
  top: -80px;
  right: -70px;
  background: rgba(89, 160, 255, 0.18);
}

.orb-b {
  width: 210px;
  height: 210px;
  bottom: -72px;
  left: -54px;
  background: rgba(245, 154, 34, 0.14);
}

.login-container {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 420px;
  padding: clamp(28px, 7vw, 46px);
  border: 1px solid rgba(167, 204, 255, 0.2);
  border-radius: 26px;
  background: linear-gradient(160deg, rgba(18, 29, 49, 0.88), rgba(11, 18, 33, 0.76));
  box-shadow: 0 28px 70px rgba(0, 0, 0, 0.34);
  backdrop-filter: blur(18px);
}

.login-header {
  text-align: center;
  margin-bottom: 30px;
}

.brand-mark {
  width: 58px;
  height: 58px;
  display: grid;
  place-items: center;
  margin: 0 auto 16px;
  border: 1px solid rgba(167, 204, 255, 0.28);
  border-radius: 18px;
  background:
    linear-gradient(135deg, rgba(89, 160, 255, 0.36), rgba(0, 168, 117, 0.16)),
    rgba(255, 255, 255, 0.06);
  color: #fff;
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 900;
  box-shadow: 0 16px 34px rgba(47, 116, 255, 0.22);
}

.login-header h1 {
  margin: 0 0 8px;
  color: #f5f8ff;
  font-family: var(--font-display);
  font-size: clamp(28px, 7vw, 36px);
  font-weight: 900;
  letter-spacing: 0.01em;
}

.subtitle {
  font-size: 14px;
  color: rgba(212, 222, 239, 0.74);
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
  height: 50px;
  padding: 0 18px;
  font-size: 16px;
  border: 1px solid rgba(167, 204, 255, 0.22);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.08);
  color: #f4f7ff;
  outline: none;
  transition:
    border-color var(--motion-fast) var(--ease-standard),
    box-shadow var(--motion-fast) var(--ease-standard),
    background-color var(--motion-fast) var(--ease-standard);
  box-sizing: border-box;
}

.password-input::placeholder {
  color: rgba(212, 222, 239, 0.42);
}

.password-input:focus {
  border-color: rgba(89, 160, 255, 0.72);
  background: rgba(255, 255, 255, 0.12);
  box-shadow: 0 0 0 4px rgba(89, 160, 255, 0.14);
}

.password-input:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.login-btn {
  width: 100%;
  height: 50px;
  font-size: 16px;
  font-weight: 800;
  color: #fff;
  background: linear-gradient(135deg, var(--brand-500) 0%, var(--brand-700) 100%);
  border: none;
  border-radius: 14px;
  cursor: pointer;
  box-shadow: 0 16px 32px rgba(47, 116, 255, 0.34);
  transition:
    opacity var(--motion-fast) var(--ease-standard),
    transform var(--motion-fast) var(--ease-standard),
    box-shadow var(--motion-fast) var(--ease-standard);
}

.login-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 20px 38px rgba(47, 116, 255, 0.42);
}

.login-btn:active:not(:disabled) {
  transform: translateY(0) scale(0.99);
}

.login-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.error-tip {
  color: #ff9dac;
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
  color: rgba(212, 222, 239, 0.5);
  margin: 0;
}

@media (max-width: 480px) {
  .login-container {
    border-radius: 22px;
  }
}
</style>
