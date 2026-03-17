<template>
  <div class="min-h-screen bg-base-100 flex flex-col">
    <NavBar />
    <!-- DEBUG PANEL — remove before prod -->
    <div class="bg-black text-green-400 text-xs font-mono p-3 space-y-1 border-b border-green-700">
      <div>🔐 isAuthenticated: <b>{{ isAuthenticated }}</b> | isLoading: <b>{{ isLoading }}</b></div>
      <div>👤 predUser: <b>{{ userStore.predUser ? userStore.predUser.email : 'null' }}</b> | storeLoading: <b>{{ userStore.loading }}</b></div>
      <div>🪙 token: <b>{{ debugToken || 'null' }}</b></div>
      <div>❌ storeError: <b>{{ userStore.error || 'none' }}</b></div>
      <div>📝 needsNameSetup: <b>{{ userStore.needsNameSetup }}</b> | 🔗 needsIdentitySetup: <b>{{ userStore.needsIdentitySetup }}</b> | 🏒 needsPrefsSetup: <b>{{ userStore.needsPrefsSetup }}</b></div>
    </div>
    <main class="flex-1 container mx-auto px-4 py-6 max-w-3xl">
      <RouterView />
    </main>
    <footer class="footer footer-center p-4 bg-base-300 text-base-content text-xs opacity-60">
      <span>🏒 Hockey Blast Predictions · Not gambling · Just fun</span>
    </footer>
    <!-- Floating AI chat widget (visible when logged in) -->
    <ChatWidget v-if="isAuthenticated" />
  </div>
</template>

<script setup>
import { watch, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth0 } from '@auth0/auth0-vue'
import { defineAsyncComponent } from 'vue'
import NavBar from '@/components/NavBar.vue'
import { useUserStore } from '@/stores/user'

const ChatWidget = defineAsyncComponent(() => import('@/components/ChatWidget.vue'))

const { isAuthenticated, isLoading, idTokenClaims } = useAuth0()
const userStore = useUserStore()
const router = useRouter()
const debugToken = ref(null)

// Load pred user profile when Auth0 confirms authentication
watch(
  () => [isAuthenticated.value, isLoading.value],
  async ([authed, loading]) => {
    if (authed && !loading) {
      try {
        const token = idTokenClaims.value?.__raw
        debugToken.value = token ? token.substring(0, 30) + '…' : 'MISSING'
        console.log('[App] got token:', debugToken.value)
        await userStore.fetchPredUser(token)
      } catch (e) {
        debugToken.value = 'EXCEPTION: ' + e.message
        console.error('[App] fetchPredUser failed:', e)
      }
      // Step 1: name missing → collect name first
      if (userStore.needsNameSetup) {
        const current = router.currentRoute.value.name
        if (current !== 'profile-setup' && current !== 'callback') {
          router.push({ name: 'profile-setup' })
        }
      // Step 2: name ok but no hockey profile linked → identity setup
      } else if (userStore.needsIdentitySetup) {
        const current = router.currentRoute.value.name
        if (current !== 'identity' && current !== 'callback') {
          router.push({ name: 'identity' })
        }
      // Step 3: identity done but player prefs not set → player prefs
      } else if (userStore.needsPrefsSetup) {
        const current = router.currentRoute.value.name
        if (current !== 'player-prefs' && current !== 'callback' && current !== 'identity') {
          router.push({ name: 'player-prefs' })
        }
      }
    } else if (!authed && !loading) {
      userStore.reset()
    }
  },
  { immediate: true }
)
</script>
