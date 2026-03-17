<template>
  <div class="container mx-auto px-4 py-6 max-w-2xl">
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-primary">🏒 Link Your Hockey Profile</h1>
      <p class="text-base-content/60 mt-1 text-sm leading-relaxed">
        If you've ever played in any of the leagues below, linking your account unlocks
        personalized stats, predictions history, and captain tools — including finding open
        ice times, connecting with teams looking for skaters or goalies, and managing
        your roster as a captain.
      </p>
      <div v-if="orgs.length" class="flex flex-wrap gap-1 mt-3">
        <span v-for="org in orgs" :key="org" class="badge badge-outline badge-sm text-xs">{{ org }}</span>
      </div>
    </div>

    <!-- Existing claims -->
    <div v-if="existingClaims.length" class="mb-6">
      <h2 class="text-sm font-semibold text-base-content/70 uppercase mb-2">Linked Profiles</h2>
      <div class="space-y-2">
        <div
          v-for="claim in existingClaims"
          :key="claim.hb_human_id"
          class="card bg-base-200 p-4 flex flex-row items-center gap-3"
        >
          <span class="text-2xl">✅</span>
          <div>
            <div class="font-medium">{{ claim.profile?.first_name }} {{ claim.profile?.last_name }}</div>
            <div class="text-xs text-base-content/50">
              {{ claim.profile?.orgs?.join(', ') }} ·
              {{ fmtDate(claim.profile?.first_date) }} – {{ fmtDate(claim.profile?.last_date) }}
            </div>
          </div>
          <div v-if="claim.is_primary" class="badge badge-primary badge-sm ml-auto">Primary</div>
        </div>
      </div>
      <button class="btn btn-ghost btn-sm mt-2" @click="showSearch = true">+ Add another profile</button>
    </div>

    <!-- Loading -->
    <div v-if="searching" class="flex justify-center py-12">
      <span class="loading loading-spinner loading-lg text-primary"></span>
    </div>

    <!-- Candidates -->
    <div v-else-if="(!existingClaims.length || showSearch) && candidates.length" class="space-y-4 mb-6">
      <div class="flex items-baseline gap-3">
        <h2 class="text-sm font-semibold text-base-content/70 uppercase">
          {{ candidates.length }} match{{ candidates.length !== 1 ? 'es' : '' }} found for {{ userFirst }} {{ userLast }}
        </h2>
        <span class="text-xs text-base-content/40">Tap a card to select / deselect</span>
      </div>

      <div
        v-for="c in candidates"
        :key="c.hb_human_id"
        class="card bg-base-200 shadow border-2 transition-all cursor-pointer relative"
        :class="selected.includes(c.hb_human_id) ? 'border-primary bg-primary/10' : 'border-transparent'"
        @click="toggleSelect(c.hb_human_id)"
      >
        <!-- Checkmark -->
        <div class="absolute top-3 right-3">
          <div
            class="w-6 h-6 rounded-full border-2 flex items-center justify-center transition-all"
            :class="selected.includes(c.hb_human_id) ? 'bg-primary border-primary text-white' : 'border-base-content/30'"
          >
            <span v-if="selected.includes(c.hb_human_id)" class="text-xs font-bold">✓</span>
          </div>
        </div>

        <div class="card-body p-4 pr-12">
          <div class="flex items-start gap-2">
            <div class="flex-1">
              <div class="font-bold text-lg">{{ c.first_name }} {{ c.last_name }}</div>
              <div class="text-xs text-base-content/50 mt-0.5">
                {{ c.orgs?.join(', ') || 'Unknown org' }}
              </div>
            </div>
            <div class="flex flex-col items-end gap-1 mr-6">
              <div
                v-if="c.skill_value != null"
                class="badge badge-sm"
                :class="skillBadgeClass(c.skill_value)"
                title="Skill level based on game history"
              >
                Skill: {{ skillLabel(c.skill_value) }}
              </div>
              <div v-if="c.name_match === 'synonym'" class="badge badge-ghost badge-sm text-xs opacity-60">
                name variant
              </div>
            </div>
          </div>

          <div class="text-xs text-base-content/60 mt-2">
            🗓 Played {{ fmtDate(c.first_date) }} – {{ fmtDate(c.last_date) }}
          </div>

          <div v-if="c.teams?.length" class="mt-2">
            <div class="text-xs text-base-content/50 mb-1">Recent teams:</div>
            <div class="flex flex-wrap gap-1">
              <span
                v-for="t in c.teams.slice(0, 5)"
                :key="t.team_id"
                class="badge badge-ghost badge-sm"
              >
                {{ t.team_name }}
                <span v-if="t.is_captain" class="text-yellow-400 ml-0.5">©</span>
              </span>
              <span v-if="c.teams.length > 5" class="badge badge-ghost badge-sm opacity-50">
                +{{ c.teams.length - 5 }} more
              </span>
            </div>
          </div>

          <div v-if="c.aliases?.length" class="text-xs text-base-content/40 mt-1">
            Also known as: {{ c.aliases.map(a => `${a.first_name} ${a.last_name}`).join(', ') }}
          </div>
        </div>
      </div>
    </div>

    <!-- No results — auto-skip prompt -->
    <div v-else-if="!searching && searched && !candidates.length && (!existingClaims.length || showSearch)"
         class="text-center py-8 text-base-content/50">
      <p class="text-lg mb-1">No hockey records found for <b>{{ userFirst }} {{ userLast }}</b></p>
      <p class="text-sm">You can still use predictions — you just won't have linked stats yet.</p>
    </div>

    <!-- Actions -->
    <div class="flex flex-col gap-3 mt-4">
      <button
        v-if="selected.length"
        class="btn btn-primary w-full"
        :class="{ loading: confirming }"
        @click="confirm"
      >
        ✅ This is me ({{ selected.length }} profile{{ selected.length !== 1 ? 's' : '' }})
      </button>
      <button class="btn btn-ghost w-full" @click="skip">Skip for now</button>
    </div>

    <!-- Success toast -->
    <div v-if="confirmed" class="toast toast-top toast-center z-50">
      <div class="alert alert-success">
        <span>Identity linked! Welcome to the hockey world 🏒</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useAuth0 } from '@auth0/auth0-vue'
import { useApiClient, publicClient } from "@/api/client"

const api = useApiClient()
const router = useRouter()
const userStore = useUserStore()
const { user } = useAuth0()

const candidates = ref([])
const selected = ref([])
const existingClaims = ref([])
const orgs = ref([])
const showSearch = ref(false)
const searching = ref(false)
const searched = ref(false)
const confirming = ref(false)
const confirmed = ref(false)
const userFirst = ref('')
const userLast = ref('')

onMounted(async () => {
  // Load orgs (public, no auth)
  try {
    const res = await publicClient.get('/api/identity/orgs')
    orgs.value = res.data.orgs || []
  } catch {}

  // Load existing claims
  try {
    const res = await api.get('/api/identity/my-claims')
    existingClaims.value = res.data.claims || []
  } catch {}

  // Auto-search
  await doSearch()
})

async function doSearch() {
  searching.value = true
  searched.value = false
  try {
    const res = await api.get('/api/identity/candidates')
    candidates.value = res.data.candidates || []
    userFirst.value = res.data.user_first || ''
    userLast.value = res.data.user_last || ''

    // Auto-select exact matches
    selected.value = candidates.value
      .filter(c => c.name_match === 'exact')
      .map(c => c.hb_human_id)

    searched.value = true

    // If no matches at all and no existing claims, skip straight to home
    if (candidates.value.length === 0 && existingClaims.value.length === 0) {
      setTimeout(() => router.push('/'), 2500)
    }
  } catch (e) {
    console.error('[identity] search failed:', e)
  } finally {
    searching.value = false
  }
}

function toggleSelect(id) {
  const idx = selected.value.indexOf(id)
  if (idx === -1) selected.value.push(id)
  else selected.value.splice(idx, 1)
}

async function confirm() {
  if (!selected.value.length) return
  confirming.value = true
  try {
    await api.post('/api/identity/confirm', { hb_human_id: selected.value })
    confirmed.value = true
    await userStore.fetchPredUser()
    setTimeout(() => router.push('/player-prefs'), 1500)
  } catch (e) {
    console.error(e)
  } finally {
    confirming.value = false
  }
}

async function skip() {
  try { await api.post('/api/identity/confirm', { skip: true }) } catch {}
  await userStore.fetchPredUser()
  router.push('/player-prefs')
}

// Format ISO date string → MM/DD/YYYY
function fmtDate(iso) {
  if (!iso) return ''
  const [y, m, d] = iso.split('T')[0].split('-')
  return `${m}/${d}/${y}`
}

function skillLabel(val) {
  if (val <= 20) return 'Elite'
  if (val <= 40) return 'Advanced'
  if (val <= 60) return 'Intermediate'
  if (val <= 80) return 'Recreational'
  return 'Beginner'
}

function skillBadgeClass(val) {
  if (val <= 20) return 'badge-success'
  if (val <= 40) return 'badge-info'
  if (val <= 60) return 'badge-warning'
  return 'badge-error'
}
</script>
