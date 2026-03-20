<template>
  <div class="flex flex-col items-center justify-center min-h-[60vh] gap-4">
    <span v-if="!authError" class="loading loading-spinner loading-lg text-primary"></span>
    <p class="text-base-content/60 text-sm">{{ authError ? '⚠️ Login failed' : 'Signing you in…' }}</p>
    <div v-if="authError" class="alert alert-error max-w-lg text-sm">{{ authError }}</div>
    <div v-if="authError" class="text-xs text-base-content/50">{{ authErrorDetail }}</div>
    <a v-if="authError" href="/" class="btn btn-sm btn-ghost mt-2">← Go back</a>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth0 } from '@auth0/auth0-vue'
import { useUserStore } from '@/stores/user'

const { isAuthenticated, isLoading, error, idTokenClaims } = useAuth0()
const userStore = useUserStore()
const router = useRouter()
const authError = ref(null)
const authErrorDetail = ref(null)

// Check URL params immediately — access.deny() comes back as ?error=access_denied
onMounted(() => {
  const params = new URLSearchParams(window.location.search)
  const urlError = params.get('error')
  const urlDesc = params.get('error_description')
  if (urlError) {
    authError.value = urlDesc || urlError
    authErrorDetail.value = urlError
  }
})

watch(error, (err) => {
  if (err) {
    authError.value = err.message || String(err)
    authErrorDetail.value = err.error_description || err.error || ''
  }
})

watch(
  () => [isAuthenticated.value, isLoading.value],
  async ([authed, loading]) => {
    if (loading) return
    if (!authed) {
      if (!error.value && !authError.value) router.replace({ name: 'home' })
      return
    }
    await userStore.fetchPredUser(idTokenClaims.value?.__raw)
    router.replace({ name: 'home' })
  },
  { immediate: true }
)
</script>
