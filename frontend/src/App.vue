<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { Listbox, ListboxButton, ListboxOptions, ListboxOption } from '@headlessui/vue'
import BotonInstalarPWA from './components/BotonInstalarPWA.vue'

/* =========================================================
   🌤️ CLIMA + MOOD (estado base)
   ========================================================= */
const demoMode = ref(false)
const city = ref('Buenos Aires, AR')
const weatherMain = ref('Clear')
const temp = ref(null)
const weatherDesc = ref('')
const weatherIcon = ref('')
const lastCoords = ref(null)
const cityLabel = ref('')     // puede venir como "lat,lon" si el reverse falla
const error = ref('')
const loading = ref(false)

/* Observación (UTC) + zona horaria IANA del backend */
const observedAtUTC = ref(null)
const tzName = ref(null)

/* =========================================================
   ⏱️ Zona horaria remota + amanecer/atardecer
   ========================================================= */
const tzOffsetSec = ref(null)
const sunriseAtMs = ref(null)
const sunsetAtMs = ref(null)

const _tick = ref(Date.now())
let _timer = null
onMounted(() => { _timer = setInterval(() => (_tick.value = Date.now()), 60_000) })
onBeforeUnmount(() => { if (_timer) clearInterval(_timer) })

// ms "ahora" en la ciudad (para fase del día)
const nowAtCityMs = computed(() => {
  const now = Date.now()
  if (tzOffsetSec.value == null) return now
  const hereOffsetMin = new Date().getTimezoneOffset()
  const utcMs = now + hereOffsetMin * 60_000
  return utcMs + tzOffsetSec.value * 1000
})

// Hora visible (preferimos IANA)
const localTime = computed(() => {
  const fmt = { hour: '2-digit', minute: '2-digit', hour12: false }
  if (tzName.value) return new Intl.DateTimeFormat('es-AR', { ...fmt, timeZone: tzName.value }).format(new Date())
  return new Intl.DateTimeFormat('es-AR', fmt).format(new Date())
})

// Hora local de la observación
const observedLocalTime = computed(() => {
  if (!observedAtUTC.value) return ''
  const d = new Date(observedAtUTC.value * 1000)
  const fmt = { hour: '2-digit', minute: '2-digit', hour12: false }
  if (tzName.value) return new Intl.DateTimeFormat('es-AR', { ...fmt, timeZone: tzName.value }).format(d)
  return new Intl.DateTimeFormat('es-AR', fmt).format(d)
})

const tempAgeMin = computed(() => {
  if (!observedAtUTC.value) return null
  const nowUtcMs = Date.now() - (new Date().getTimezoneOffset() * 60000)
  const obsUtcMs = observedAtUTC.value * 1000
  return Math.max(0, Math.round((nowUtcMs - obsUtcMs) / 60000))
})

/* =========================================================
   🌙 Fase del día
   ========================================================= */
function phaseOfDay(nowMs, riseMs, setMs) {
  const W = 45 * 60 * 1000
  const t = nowMs
  if (riseMs != null && setMs != null) {
    if (t < riseMs - W) return 'night'
    if (t <= riseMs + W) return 'sunrise'
    if (t < setMs - W) return 'day'
    if (t <= setMs + W) return 'sunset'
    return 'night'
  }
  const h = (tzOffsetSec.value == null) ? new Date(t).getHours() : new Date(t).getUTCHours()
  if (h < 6) return 'night'
  if (h < 8) return 'sunrise'
  if (h < 18) return 'day'
  if (h < 20) return 'sunset'
  return 'night'
}

/* =========================================================
   🌡️ Temperatura
   ========================================================= */
const tempText = computed(() => temp.value == null ? '—' : `${Math.round(Number(temp.value))}°C`)

/* =========================================================
   🎨 Mood UI
   ========================================================= */
const currentMood = ref({ title: '—', emoji: '🎵', query: '', grad: 'linear-gradient(135deg,#0f172a,#111827)' })
const moodTitle = computed(() => currentMood.value.title)
const moodEmoji = computed(() => currentMood.value.emoji)
const moodGradient = computed(() => currentMood.value.grad)
const currentQuery = computed(() => currentMood.value.query)

const containerStyle = computed(() => ({
  backgroundImage: currentMood.value.grad,
  backgroundRepeat: 'no-repeat',
  backgroundSize: 'cover',
  backgroundAttachment: 'fixed',
}))

/* =========================================================
   Nombre de lugar: evitar coordenadas
   ========================================================= */
function isCoordsText(s) {
  return /^\s*-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?\s*$/.test(String(s || ''))
}
const displayCity = computed(() =>
  isCoordsText(city.value) ? 'Ubicación actual' : (city.value || 'Ubicación actual')
)
// 👉 este es el texto que mostramos siempre en la tarjeta
function prettyPlace(raw) {
  if (isCoordsText(raw)) return displayCity.value || 'Ubicación actual'
  return raw || (displayCity.value || 'Ubicación actual')
}
const placeText = computed(() => prettyPlace(cityLabel.value || displayCity.value))

const cityIO = computed({
  get: () => (isCoordsText(city.value) ? 'Ubicación actual' : (city.value || 'Ubicación actual')),
  set: (v) => { city.value = (v ?? '').trim() }
})

// 👇 cuando está activo el modo global, usamos este texto fijo en la tarjeta
const cardPlaceText = computed(() => demoMode.value ? 'modo global' : placeText.value)

/* =========================================================
   Etiquetas ES ↔ EN
   ========================================================= */
const WEATHER_OPTIONS = [
  { value: 'Clear', label: 'Despejado' },
  { value: 'Clouds', label: 'Nublado' },
  { value: 'Rain', label: 'Lluvia' },
  { value: 'Drizzle', label: 'Llovizna' },
  { value: 'Thunderstorm', label: 'Tormenta' },
  { value: 'Snow', label: 'Nieve' },
  { value: 'Mist', label: 'Neblina' },
  { value: 'Fog', label: 'Niebla' },
  { value: 'Haze', label: 'Calina' },
  { value: 'Smoke', label: 'Humo' },
]
const WEATHER_ES = WEATHER_OPTIONS.reduce((acc, o) => (acc[o.value] = o.label, acc), {})
function labelES(value) { return WEATHER_ES[value] || value || '' }
const weatherLabel = computed(() => labelES(weatherMain.value))
watch([() => demoMode.value, () => weatherMain.value], () => {
  if (demoMode.value) weatherDesc.value = labelES(weatherMain.value) || weatherDesc.value
})

/* =========================================================
   Mood por clima + fase
   ========================================================= */
function enrichQueryByPhase(q, phase) {
  if (phase === 'sunrise') return q + ' morning acoustic'
  if (phase === 'day') return q + ' focus beats'
  if (phase === 'sunset') return q + ' chill'
  if (phase === 'night') return q + ' night'
  return q
}
function moodFor(main, temp, phase) {
  const map = {
    Clear:
      phase === 'night'
        ? { title: 'Relajación nocturna', emoji: '🌙', query: 'late night chill synthwave', grad: 'linear-gradient(135deg,#0f172a,#1f2937 40%,#0b1220)' }
        : phase === 'sunrise'
          ? { title: 'Amanecer acústico', emoji: '🌅', query: 'acoustic sunrise chill', grad: 'linear-gradient(135deg,#f59e0b,#fde68a 45%,#a7f3d0)' }
          : phase === 'sunset'
            ? { title: 'Hora dorada', emoji: '🌇', query: 'indie chill golden hour', grad: 'linear-gradient(135deg,#fb923c,#f472b6 45%,#60a5fa)' }
            : { title: 'Energía soleada', emoji: '🌞', query: 'summer vibes feel good', grad: 'linear-gradient(135deg,#0ea5e9,#22d3ee 40%,#fef08a)' },
    Clouds: { title: 'Chill & concentración', emoji: '☁️', query: 'chillhop lofi focus', grad: 'linear-gradient(135deg,#334155,#475569 40%,#0ea5e9)' },
    Rain: { title: 'Lluvia Lo-fi', emoji: '🌧️', query: 'lofi rain study', grad: 'linear-gradient(135deg,#0f172a,#1e293b 40%,#3b82f6)' },
    Drizzle: { title: 'Llovizna Lo-fi', emoji: '🌦️', query: 'lofi drizzle chill', grad: 'linear-gradient(135deg,#0f172a,#1e293b 40%,#60a5fa)' },
    Thunderstorm: { title: 'Modo épico', emoji: '⛈️', query: 'dark ambient epic soundtrack', grad: 'linear-gradient(135deg,#111827,#111827 40%,#7c3aed)' },
    Snow: { title: 'Acústico acogedor', emoji: '❄️', query: 'warm acoustic cozy', grad: 'linear-gradient(135deg,#94a3b8,#cbd5e1 40%,#f8fafc)' },
    Mist: { title: 'Lofi ambiental', emoji: '🌫️', query: 'ambient lofi', grad: 'linear-gradient(135deg,#1f2937,#334155 40%,#64748b)' },
    Fog: { title: 'Lofi ambiental', emoji: '🌫️', query: 'ambient lofi', grad: 'linear-gradient(135deg,#1f2937,#334155 40%,#64748b)' },
    Haze: { title: 'Lofi ambiental', emoji: '🌫️', query: 'ambient lofi', grad: 'linear-gradient(135deg,#1f2937,#334155 40%,#64748b)' },
    Smoke: { title: 'Lofi ambiental', emoji: '🌫️', query: 'ambient lofi', grad: 'linear-gradient(135deg,#1f2937,#334155 40%,#64748b)' },
  }
  let base = map[main] || { title: 'Flujo de concentración', emoji: '🎧', query: 'lofi coding focus', grad: 'linear-gradient(135deg,#0f172a,#1e293b 40%,#0ea5e9)' }
  return { ...base, query: enrichQueryByPhase(base.query, phase) }
}

/* =========================================================
   🌎 GEO + Weather fetch
   ========================================================= */
function isSecure() { return window.isSecureContext || location.hostname === 'localhost' }
function getPosition(opts = { enableHighAccuracy: true, timeout: 8000, maximumAge: 60000 }) {
  return new Promise((resolve, reject) => {
    if (!('geolocation' in navigator)) return reject(new Error('Geolocalización no soportada'))
    navigator.geolocation.getCurrentPosition(pos => resolve(pos.coords), err => reject(err), opts)
  })
}
function normalizeMain(es) {
  const s = (es || '').toLowerCase()
  if (s.includes('nublado')) return 'Clouds'
  if (s.includes('lluvia')) return 'Rain'
  if (s.includes('llovizna')) return 'Drizzle'
  if (s.includes('tormenta')) return 'Thunderstorm'
  if (s.includes('nieve')) return 'Snow'
  if (s.includes('neblina') || s.includes('niebla')) return 'Mist'
  if (s.includes('calina')) return 'Haze'
  if (s.includes('humo')) return 'Smoke'
  return 'Clear'
}
function toTempC(v) { const n = Number(v); return Number.isFinite(n) ? Math.round(n) : null }

function pickTempAndObs(data) {
  if (data?.main?.temp != null) return { temp: data.main.temp, dt: data.dt ?? null }
  if (data?.temp != null) return { temp: data.temp, dt: data?.dt ?? null }
  if (data?.current?.temp != null) return { temp: data.current.temp, dt: data.current.dt }
  if (Array.isArray(data?.hourly) && data.hourly.length) {
    const now = Math.floor(Date.now() / 1000)
    const closest = data.hourly.reduce((best, x) => Math.abs((x?.dt ?? 0) - now) < Math.abs((best?.dt ?? 0) - now) ? x : best, data.hourly[0])
    return { temp: closest?.temp ?? null, dt: closest?.dt ?? null }
  }
  if (Array.isArray(data?.list) && data.list.length) {
    const now = Math.floor(Date.now() / 1000)
    const closest = data.list.reduce((best, x) => Math.abs((x?.dt ?? 0) - now) < Math.abs((best?.dt ?? 0) - now) ? x : best, data.list[0])
    return { temp: closest?.main?.temp ?? null, dt: closest?.dt ?? null }
  }
  return { temp: null, dt: null }
}

async function fetchByCoords(lat, lon) {
  loading.value = true; error.value = ''
  try {
    const res = await fetch(`/api/weather/geo?lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}&lang=es&units=metric`)
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data?.error || data?.message || 'Clima no disponible')

    cityLabel.value = data.city || 'Ubicación actual'
    const picked = pickTempAndObs(data)
    weatherMain.value = normalizeMain(data.weather)
    weatherDesc.value = data.weather || ''
    temp.value = toTempC(picked.temp)
    observedAtUTC.value = picked.dt ?? null
    weatherIcon.value = data.icon || ''

    tzName.value = data.timezone || null
    tzOffsetSec.value = (data.tz_offset_sec ?? null)
    sunriseAtMs.value = (data.sunrise != null && tzOffsetSec.value != null) ? (data.sunrise + tzOffsetSec.value) * 1000 : null
    sunsetAtMs.value = (data.sunset != null && tzOffsetSec.value != null) ? (data.sunset + tzOffsetSec.value) * 1000 : null

    const phase = phaseOfDay(nowAtCityMs.value, sunriseAtMs.value, sunsetAtMs.value)
    const m = moodFor(normalizeMain(weatherDesc.value || weatherMain.value), temp.value, phase)
    currentMood.value = m

    // 👇 mapear título ES → key EN antes de buscar playlists
    const key = PLAYLIST_KEY[m.title] || m.title
    playlists.value = await hydrateCovers(MOOD_PLAYLISTS[key] || MOOD_PLAYLISTS['Sunny vibes'] || [])
  } catch (e) {
    error.value = e.message || 'Error de clima'
  } finally { loading.value = false }
}


// helpers: coords vs texto
function isCoords(q) {
  const m = String(q).trim().match(/^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$/)
  if (!m) return null
  const lat = parseFloat(m[1]), lon = parseFloat(m[2])
  if (isNaN(lat) || isNaN(lon)) return null
  if (lat < -90 || lat > 90 || lon < -180 || lon > 180) return null
  return `${lat},${lon}`
}
function hasCountrySuffix(q) { return /\b(AR|Argentina)\b/i.test(q) }

async function handleSearch() {
  loading.value = true
  error.value = ''
  try {
    // ⚠️ En modo global ignoramos totalmente fetch/geo
    if (demoMode.value) {
      await updateDemo()
      return
    }

    if (isSecure()) {
      try {
        const coords = await getPosition()
        lastCoords.value = { lat: coords.latitude, lon: coords.longitude }
        await fetchByCoords(coords.latitude, coords.longitude)
        return
      } catch (e) {
        console.warn('GPS fail, fallback por ciudad/coords:', e)
      }
    }

    const q0 = city.value?.trim() || ''
    const variants = []
    const coordsTxt = isCoords(q0)
    if (coordsTxt) {
      variants.push(coordsTxt)
    } else {
      variants.push(q0)
      if (!hasCountrySuffix(q0)) variants.push(`${q0}, AR`)
      if (/buenos\s*aires/i.test(q0) || /caba/i.test(q0))
        variants.push(
          'CABA',
          'Ciudad Autónoma de Buenos Aires',
          'Buenos Aires, Argentina',
          '-34.6037,-58.3816'
        )
    }

    const seen = new Set()
    const queue = variants
      .map(s => s.replace(/\s+/g, ' ').replace(/,\s*,/g, ','))
      .map(s => s.replace(/,\s*(AR|Argentina)\s*(,?\s*(AR|Argentina))+/gi, ', AR'))
      .filter(s => s.length > 0 && !seen.has(s) && (seen.add(s), true))

    const hit = async (q) => {
      const r = await fetch(`/api/weather?city=${encodeURIComponent(q)}&lang=es&units=metric`)
      const d = await r.json().catch(() => ({}))
      return { ok: r.ok, status: r.status, data: d, q }
    }

    let okResp = null, lastErr = null
    for (const q of queue) {
      const r = await hit(q)
      if (r.ok) { okResp = r; break }
      lastErr = r
      console.warn('Weather fallback fail:', q, r.status, r.data)
    }
    if (!okResp) {
      const msg = lastErr?.data?.body?.error?.message || lastErr?.data?.error || 'No se pudo obtener el clima'
      throw new Error(msg)
    }

    const data = okResp.data
    const wasCoords = !!isCoords(q0)
    cityLabel.value = data.city || (wasCoords ? 'Ubicación actual' : '')

    const picked = pickTempAndObs(data)
    weatherMain.value = normalizeMain(data.weather)
    weatherDesc.value = data.weather || ''
    temp.value = toTempC(picked.temp)
    observedAtUTC.value = picked.dt ?? null
    weatherIcon.value = data.icon || ''

    tzName.value = data.timezone || null
    tzOffsetSec.value = (data.tz_offset_sec ?? null)
    sunriseAtMs.value = (data.sunrise != null && tzOffsetSec.value != null)
      ? (data.sunrise + tzOffsetSec.value) * 1000
      : null
    sunsetAtMs.value = (data.sunset != null && tzOffsetSec.value != null)
      ? (data.sunset + tzOffsetSec.value) * 1000
      : null

    const phase = phaseOfDay(nowAtCityMs.value, sunriseAtMs.value, sunsetAtMs.value)
    const m = moodFor(normalizeMain(weatherDesc.value || weatherMain.value), temp.value, phase)
    currentMood.value = m

    // ✅ Usamos PLAYLIST_KEY para mapear del título ES al key EN
    const key = PLAYLIST_KEY[m.title] || m.title
    playlists.value = await hydrateCovers(
      MOOD_PLAYLISTS[key] || MOOD_PLAYLISTS['Sunny vibes'] || []
    )
  } catch (e) {
    error.value = String(e?.message || 'Error de clima')
  } finally {
    loading.value = false
  }
}


async function useTimeOnly() {
  weatherMain.value = 'Clear'
  weatherDesc.value = labelES('Clear')
  await updateDemo()
}

/* =========================================================
   🎧 SPOTIFY + PLAYER
   ========================================================= */
const playlists = ref([])
const embedId = ref(null)
const playerVisible = ref(false)
const playerCollapsed = ref(false)

const FALLBACK_COVER =
  'data:image/svg+xml;utf8,' +
  encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120">
  <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
  <stop stop-color="#0f172a"/><stop offset="1" stop-color="#1e293b"/></linearGradient></defs>
  <rect width="120" height="120" fill="url(#g)"/><text x="50%" y="55%" text-anchor="middle" fill="#94a3b8" font-family="Arial" font-size="16">Playlist</text></svg>`)

const MOOD_PLAYLISTS = {
  'Late night chill': [
    { id: '37i9dQZF1DX4WYpdgoIcn6', name: 'Chill Hits', image: FALLBACK_COVER, owner: 'Spotify' },
    { id: '37i9dQZF1DX4sWSpwq3LiO', name: 'Deep Focus', image: FALLBACK_COVER, owner: 'Spotify' },
    { id: '37i9dQZF1DX889U0CL85jj', name: 'Night Rider', image: FALLBACK_COVER, owner: 'Spotify' },
  ],
  'Sunrise glow': [
    { id: '37i9dQZF1DX4mWCZw6qYIw', name: 'Warm Acoustic', image: FALLBACK_COVER, owner: 'Spotify' },
    { id: '37i9dQZF1DXa2SPUyWl8Y5', name: 'Acoustic Chill', image: FALLBACK_COVER, owner: 'Spotify' },
    { id: '37i9dQZF1DWXmlLSKkfdAk', name: 'Your Favorite Coffeehouse', image: FALLBACK_COVER, owner: 'Spotify' },
  ],
  'Golden hour': [
    { id: '37i9dQZF1DX0UrRvztWcAU', name: 'Summer Vibes', image: FALLBACK_COVER, owner: 'Spotify' },
    { id: '37i9dQZF1DX2sUQwD7tbmL', name: 'Feel Good', image: FALLBACK_COVER, owner: 'Spotify' },
    { id: '37i9dQZF1DX4E3UdUs7fUx', name: 'Lo-Fi Café', image: FALLBACK_COVER, owner: 'Spotify' },
  ],
  'Sunny vibes': [
    { id: '37i9dQZF1DX0UrRvztWcAU', name: 'Summer Vibes', image: FALLBACK_COVER, owner: 'Spotify' },
    { id: '37i9dQZF1DX2sUQwD7tbmL', name: 'Feel Good', image: FALLBACK_COVER, owner: 'Spotify' },
    { id: '37i9dQZF1DX0hWmn8d5pRe', name: 'Good Vibes', image: FALLBACK_COVER, owner: 'Spotify' },
  ],
  'Chill & Focus': [
    { id: '37i9dQZF1DX4sWSpwq3LiO', name: 'Deep Focus', image: FALLBACK_COVER, owner: 'Spotify' },
    { id: '37i9dQZF1DX8Uebhn9wzrS', name: 'Lo-Fi Beats', image: FALLBACK_COVER, owner: 'Spotify' },
    { id: '37i9dQZF1DX3PFzdbtx1Us', name: 'Coding Mode', image: FALLBACK_COVER, owner: 'Spotify' },
  ],
  'Lo-fi rain': [
    { id: '37i9dQZF1DXcZDD7cfEKhW', name: 'Lo-Fi Beats', image: FALLBACK_COVER, owner: 'Spotify' },
    { id: '37i9dQZF1DWVV27DiNWxkR', name: 'Rainy Day', image: FALLBACK_COVER, owner: 'Spotify' },
    { id: '37i9dQZF1DX4E3UdUs7fUx', name: 'Lo-Fi Café', image: FALLBACK_COVER, owner: 'Spotify' },
  ],
  'Lo-fi drizzle': [
    { id: '37i9dQZF1DX0SM0LYsmbMT', name: 'Jazz Vibes', image: FALLBACK_COVER, owner: 'Spotify' },
    { id: '37i9dQZF1DX6VdMW310YC7', name: 'Chillhop', image: FALLBACK_COVER, owner: 'Spotify' },
    { id: '37i9dQZF1DX1s9knjP51Oa', name: 'lofi sleep', image: FALLBACK_COVER, owner: 'Spotify' },
  ],
  'Epic mode': [
    { id: '37i9dQZF1DX8FwnYE6PRvL', name: 'Epic Film Scores', image: FALLBACK_COVER, owner: 'Spotify' },
    { id: '37i9dQZF1DWYLFeUy0s5K5', name: 'Power Gaming', image: FALLBACK_COVER, owner: 'Spotify' },
    { id: '37i9dQZF1DX59NCqCqJtoH', name: 'Intense Studying', image: FALLBACK_COVER, owner: 'Spotify' },
  ],
  'Warm acoustic': [
    { id: '37i9dQZF1DX4mWCZw6qYIw', name: 'Warm Acoustic', image: FALLBACK_COVER, owner: 'Spotify' },
    { id: '37i9dQZF1DWXmlLSKkfdAk', name: 'Your Favorite Coffeehouse', image: FALLBACK_COVER, owner: 'Spotify' },
    { id: '37i9dQZF1DXa2SPUyWl8Y5', name: 'Acoustic Chill', image: FALLBACK_COVER, owner: 'Spotify' },
  ],
  'Ambient lofi': [
    { id: '37i9dQZF1DX7gIoKXt0gmx', name: 'Ambient Chill', image: FALLBACK_COVER, owner: 'Spotify' },
    { id: '37i9dQZF1DX6ALfRKlHn1t', name: 'lofi ambient chill', image: FALLBACK_COVER, owner: 'Spotify' },
    { id: '37i9dQZF1DX3Ogo9pFvBkY', name: 'Peaceful Piano', image: FALLBACK_COVER, owner: 'Spotify' },
  ],
  'Focus flow': [
    { id: '37i9dQZF1DX4sWSpwq3LiO', name: 'Deep Focus', image: FALLBACK_COVER, owner: 'Spotify' },
    { id: '37i9dQZF1DX8Uebhn9wzrS', name: 'Lo-Fi Beats', image: FALLBACK_COVER, owner: 'Spotify' },
    { id: '37i9dQZF1DX9sIqqvKsjG8', name: 'Brain Food', image: FALLBACK_COVER, owner: 'Spotify' },
  ],
}

const PLAYLIST_KEY = {
  'Energía soleada': 'Sunny vibes',
  'Hora dorada': 'Golden hour',
  'Amanecer acústico': 'Sunrise glow',
  'Relajación nocturna': 'Late night chill',
  'Chill & concentración': 'Chill & Focus',
  'Lluvia Lo-fi': 'Lo-fi rain',
  'Llovizna Lo-fi': 'Lo-fi drizzle',
  'Modo épico': 'Epic mode',
  'Acústico acogedor': 'Warm acoustic',
  'Lofi ambiental': 'Ambient lofi',
  'Flujo de concentración': 'Focus flow',
}

function openEmbed(id) { embedId.value = id; playerVisible.value = true; nextTick(() => { }) }

async function hydrateCovers(list) {
  const ids = Array.from(new Set(list.map(p => p.id))).join(',')
  if (!ids) return list
  try {
    const res = await fetch(`/api/spotify/playlist_covers?ids=${encodeURIComponent(ids)}`)
    const data = await res.json()
    const covers = data?.covers || {}
    return list.map(p => ({ ...p, image: covers[p.id] || p.image || FALLBACK_COVER }))
  } catch { return list.map(p => ({ ...p, image: p.image || FALLBACK_COVER })) }
}

async function playRandomEmbed() {
  if (!playlists.value.length) { await updateDemo(); if (!playlists.value.length) return }
  const pl = playlists.value[Math.floor(Math.random() * playlists.value.length)]
  embedId.value = pl.id; playerVisible.value = true
}
function closeEmbed() { embedId.value = null; playerVisible.value = false }

/* ====== Spotify Web Playback SDK (opcional) ====== */
const spotifyReady = ref(false)
let spotifyPlayer = null
const deviceId = ref(null)
const premiumError = ref('')

async function getSpotifyToken() {
  const r = await fetch('/api/spotify/token')
  if (!r.ok) throw new Error('No se pudo obtener token de Spotify')
  const { access_token } = await r.json()
  if (!access_token) throw new Error('Token vacío')
  return access_token
}
function loadSpotifySDK() {
  return new Promise((resolve, reject) => {
    if (window.Spotify) return resolve()
    const script = document.createElement('script')
    script.src = 'https://sdk.scdn.co/spotify-player.js'
    script.async = true
    script.onload = () => resolve()
    script.onerror = () => reject(new Error('No se pudo cargar Spotify SDK'))
    document.head.appendChild(script)
  })
}
async function ensurePlayer() {
  if (spotifyPlayer && deviceId.value) return spotifyPlayer
  await loadSpotifySDK()
  const token = await getSpotifyToken()
  await new Promise((resolve) => {
    window.onSpotifyWebPlaybackSDKReady = () => resolve()
    if (window.Spotify) resolve()
  })
  spotifyPlayer = new window.Spotify.Player({ name: 'Mood Music (Web)', getOAuthToken: cb => cb(token), volume: 0.8 })
  spotifyPlayer.addListener('ready', ({ device_id }) => { deviceId.value = device_id; spotifyReady.value = true })
  spotifyPlayer.addListener('not_ready', () => { spotifyReady.value = false })
  spotifyPlayer.addListener('initialization_error', ({ message }) => { premiumError.value = message })
  spotifyPlayer.addListener('authentication_error', ({ message }) => { premiumError.value = message })
  spotifyPlayer.addListener('account_error', ({ message }) => { premiumError.value = message })
  const ok = await spotifyPlayer.connect()
  if (!ok) throw new Error('No se pudo conectar el player')
  await transferPlaybackHere()
  return spotifyPlayer
}
async function transferPlaybackHere() {
  const token = await getSpotifyToken()
  if (!deviceId.value) return
  await fetch('https://api.spotify.com/v1/me/player', {
    method: 'PUT',
    headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ device_ids: [deviceId.value], play: false })
  })
}
async function spApi(path, init = {}) {
  const token = await getSpotifyToken()
  const headers = init.headers ? { ...init.headers } : {}
  headers['Authorization'] = `Bearer ${token}`
  if (!headers['Content-Type'] && init.method && init.method !== 'GET') headers['Content-Type'] = 'application/json'
  const r = await fetch(`https://api.spotify.com/v1${path}`, { ...init, headers })
  if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e?.error?.message || `Spotify API error ${r.status}`) }
  return r.json()
}

/* navegación entre playlists (card) */
const currentIndex = ref(-1)
const currentPl = computed(() => (currentIndex.value < 0 || currentIndex.value >= playlists.value.length) ? null : playlists.value[currentIndex.value])
watch(playlists, () => { currentIndex.value = -1 })
function pick(index) { if (!playlists.value.length) return; currentIndex.value = (index + playlists.value.length) % playlists.value.length; openEmbed(playlists.value[currentIndex.value].id) }
function nextPlaylist() { if (playlists.value.length) pick(currentIndex.value >= 0 ? currentIndex.value + 1 : 0) }
function prevPlaylist() { if (playlists.value.length) pick(currentIndex.value >= 0 ? currentIndex.value - 1 : playlists.value.length - 1) }

async function playRandom() {
  premiumError.value = ''
  try {
    if (!playlists.value.length) { await updateDemo(); if (!playlists.value.length) return }
    const pl = playlists.value[Math.floor(Math.random() * playlists.value.length)]
    currentIndex.value = playlists.value.findIndex(p => p.id === pl.id)
    await ensurePlayer()
    const tracksResp = await spApi(`/playlists/${pl.id}/tracks?limit=100&fields=items(track(uri))`)
    const trackUris = tracksResp.items.map(it => it?.track?.uri).filter(Boolean)
    if (!trackUris.length) throw new Error('Playlist sin tracks')
    const randomTrack = trackUris[Math.floor(Math.random() * trackUris.length)]
    await transferPlaybackHere()
    await fetch('https://api.spotify.com/v1/me/player/play', {
      method: 'PUT',
      headers: { 'Authorization': `Bearer ${await getSpotifyToken()}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ uris: [randomTrack], position_ms: 0 })
    })
    openEmbed(pl.id)
  } catch (e) {
    premiumError.value = e.message || 'No se pudo reproducir en Spotify'
    if (playlists.value.length) {
      const pl = playlists.value[Math.floor(Math.random() * playlists.value.length)]
      currentIndex.value = playlists.value.findIndex(p => p.id === pl.id)
      openEmbed(pl.id)
    }
  }
}

/* =========================================================
   🔁 INICIALIZACIÓN / DEMO
   ========================================================= */
const canEditTemp = computed(() => demoMode.value)
function bumpTemp(delta) {
  if (temp.value == null || Number.isNaN(Number(temp.value))) temp.value = 20
  const v = Math.round(Number(temp.value) + delta)
  temp.value = Math.max(-10, Math.min(45, v))
}
async function updateDemo() {
  const phase = phaseOfDay(nowAtCityMs.value, sunriseAtMs.value, sunsetAtMs.value)
  currentMood.value = moodFor(normalizeMain(weatherDesc.value || weatherMain.value), temp.value, phase)
  const key = PLAYLIST_KEY[currentMood.value.title] || currentMood.value.title
  const base = MOOD_PLAYLISTS[key] || MOOD_PLAYLISTS['Sunny vibes'] || []
  playlists.value = await hydrateCovers(base)
}


// Al montar: si no es global, buscamos en vivo
onMounted(() => {
  if (demoMode.value) {
    weatherDesc.value = labelES(weatherMain.value)
    updateDemo()
  } else {
    handleSearch()
  }
})

// Al cambiar Global <-> En vivo
watch(demoMode, (on) => {
  if (on) {
    // 👉 Modo global: ignorar ubicación/backend y limpiar campos de geo
    if (temp.value == null) temp.value = 20
    weatherDesc.value = labelES(weatherMain.value)
    cityLabel.value = ''
    observedAtUTC.value = null
    tzName.value = null
    tzOffsetSec.value = null
    sunriseAtMs.value = null
    sunsetAtMs.value = null
    updateDemo()
  } else {
    // Volver a “en vivo”
    handleSearch()
  }
})

// Recalcular playlists cuando cambian clima/temp o cada minuto (fase)
watch([weatherMain, temp, _tick], updateDemo)
</script>




<template>
  <!-- RAÍZ sin :key -->
  <div :style="containerStyle" class="min-h-screen transition-colors duration-700 pb-28">

    <header class="max-w-6xl mx-auto px-4 py-8">
      <nav class="flex items-center justify-between mb-8">
        <div class="flex items-center gap-2">
          <span class="text-xl"><i class="fa-solid fa-music text-xl"></i></span>
          <span class="font-semibold tracking-wide">Mood Music</span>
          <span class="ml-2 text-xs px-2 py-0.5 rounded-full border" :class="demoMode
            ? 'border-white/30 text-white/80 bg-white/10'
            : 'border-emerald-300/40 text-emerald-200 bg-emerald-500/10'">
            {{ demoMode ? 'Global' : 'En vivo' }}
          </span>
        </div>

        <!-- derecha de la navbar -->
        <div class="flex items-center gap-4 text-sm">
          <div class="flex items-center gap-3">
            <span class="opacity-80">Modo global</span>
            <label class="inline-flex items-center cursor-pointer">
              <input type="checkbox" class="sr-only peer" v-model="demoMode" />
              <div class="relative w-10 h-6 rounded-full border border-white/20 bg-white/10 transition peer-checked:bg-white/30
                       after:content-[''] after:absolute after:top-0.5 after:left-0.5
                       after:h-5 after:w-5 after:rounded-full after:bg-white after:transition
                       peer-checked:after:translate-x-4">
              </div>
            </label>
          </div>

          <!-- Botón instalar (no desaparece) -->
          <BotonInstalarPWA variant="text" />
        </div>
      </nav>

      <!-- CONTENIDO -->
      <div class="grid md:grid-cols-2 gap-8 items-start">
        <!-- Controles -->
        <div>
          <h1 class="text-4xl md:text-5xl font-bold leading-tight">
            Tu <span class="text-white/90">soundtrack</span> para este momento
          </h1>
          <p class="text-slate-200/80 mt-4">
            {{ demoMode
              ? 'Vista en modo global: simulá clima y temperatura para probar el mood.'
              : 'Modo en vivo: intentamos tu ubicación actual al actualizar y si falla usamos la ciudad ingresada.' }}
          </p>

          <div class="mt-6 space-y-4">
            <div class="grid sm:grid-cols-2 gap-3">
              <div class="flex flex-col">
                <label class="text-sm text-white/70 mb-1">Ciudad</label>
                <input v-model="cityIO" type="text"
                  class="rounded-xl bg-white/10 px-4 py-3 outline-none focus:ring-2 focus:ring-white/30 placeholder:text-slate-300/50"
                  placeholder="Ej: Buenos Aires, AR o -34.6037,-58.3816" />
                <small class="text-white/50 mt-1">
                  Primero usamos tu ubicación actual. Si no se puede, buscamos por este valor.
                </small>
              </div>

              <div class="flex flex-col">
                <label class="text-sm text-white/70 mb-1">Clima (solo global)</label>
                <Listbox v-model="weatherMain" :disabled="!demoMode">
                  <div class="relative">
                    <ListboxButton class="relative w-full cursor-pointer rounded-xl bg-white py-3 px-4 text-left text-slate-900 shadow
                             focus:outline-none focus:ring-2 focus:ring-sky-300 disabled:opacity-60 disabled:bg-white">
                      {{ weatherLabel }}
                      <span class="pointer-events-none absolute inset-y-0 right-3 flex items-center">
                        <i class="fa-solid fa-chevron-down text-slate-500"></i>
                      </span>
                    </ListboxButton>

                    <ListboxOptions
                      class="absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded-xl bg-white py-1 shadow-lg ring-1 ring-black/10 focus:outline-none">
                      <ListboxOption v-for="opt in WEATHER_OPTIONS" :key="opt.value" :value="opt.value"
                        v-slot="{ active, selected }" as="template">
                        <li :class="[
                          'cursor-pointer select-none py-2 px-4',
                          active ? 'bg-sky-100 text-sky-900' : 'text-slate-900',
                          selected ? 'font-semibold' : 'font-normal'
                        ]">
                          {{ opt.label }}
                        </li>
                      </ListboxOption>
                    </ListboxOptions>
                  </div>
                </Listbox>
              </div>
            </div>

            <div class="flex flex-wrap gap-3">
              <button @click="handleSearch" :disabled="loading"
                class="rounded-xl bg-white text-slate-900 font-semibold px-5 py-3 hover:bg-slate-100 transition disabled:opacity-50">
                {{ loading ? 'Cargando…' : 'Actualizar mood' }}
              </button>

              <button @click="useTimeOnly" :disabled="!demoMode || loading"
                class="rounded-xl bg-white/10 border border-white/15 px-5 py-3 hover:bg-white/20 transition disabled:opacity-50">
                Solo hora
              </button>
            </div>

            <div class="text-xs text-white/60" v-if="displayCity">+ Ubicación: {{ displayCity }}</div>
            <p v-if="error" class="text-red-300">{{ error }}</p>
          </div>
        </div>

        <!-- Columna derecha -->
        <div class="flex flex-col gap-4">
          <div class="bg-black/30 border border-white/10 rounded-2xl p-6 md:p-8 backdrop-blur-sm">
            <div class="flex items-center justify-between">
              <div class="text-sm text-white/70">Mood detectado</div>
              <div class="text-2xl">{{ moodEmoji }}</div>
            </div>
            <h2 class="text-2xl md:text-3xl font-semibold mt-2">{{ moodTitle }}</h2>

            <p class="text-white/70 mt-2 flex items-center gap-2">
              <img v-if="weatherIcon" :src="weatherIcon" alt="" class="w-6 h-6" />
              En {{ cardPlaceText }} hay
              <span class="font-semibold">{{ weatherDesc || weatherMain }}</span>
              — {{ tempText }}.
            </p>

            <p class="text-white/70 mt-2">Son las {{ localTime }}.</p>
            <p class="mt-4 text-white/80" v-if="currentQuery">
              Te propongo: <span class="font-semibold">{{ currentQuery }}</span>
            </p>
          </div>

          <div class="bg-black/30 border border-white/10 rounded-2xl p-6 md:p-8 backdrop-blur-sm relative">
            <div class="flex items-center justify-between">
              <div class="text-sm text-white/70">Reproductor del momento</div>
              <div class="text-xs text-white/60">Basado en: <span class="font-semibold">{{ moodTitle }}</span></div>
            </div>

            <div class="mt-4" v-if="!embedId">
              <button @click="playRandomEmbed" :disabled="loading || !playlists.length" class="h-12 w-12 rounded-full bg-emerald-500 hover:bg-emerald-400 text-slate-900 flex items-center justify-center shadow
                       focus:outline-none focus:ring-2 focus:ring-emerald-300 disabled:opacity-50"
                title="Reproducir algo del momento" aria-label="Reproducir algo del momento">
                <i class="fa-solid fa-shuffle text-lg"></i>
              </button>
            </div>

            <div v-if="embedId" class="mt-5 overflow-hidden rounded-xl">
              <iframe :src="`https://open.spotify.com/embed/playlist/${embedId}?theme=0`" width="100%" height="152"
                frameborder="0" allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture"
                loading="lazy" class="w-full h-[152px]"></iframe>
            </div>

            <button v-if="embedId" @click="closeEmbed"
              class="absolute top-3 right-3 h-8 w-8 rounded-full bg-white/10 hover:bg-white/20 text-white flex items-center justify-center"
              title="Cerrar reproductor" aria-label="Cerrar reproductor">
              <i class="fa-solid fa-xmark"></i>
            </button>

            <div v-if="!embedId" class="mt-3 text-white/70">
              No hay nada sonando. Tocá el <span class="font-semibold">shuffle</span>.
            </div>
          </div>
        </div>
      </div>
    </header>

    <main class="max-w-6xl mx-auto px-4 pb-20">
      <div class="flex items-center justify-between mt-6 mb-4">
        <h3 class="text-xl font-semibold">Playlists sugeridas</h3>
        <div v-if="loading" class="text-sm text-white/70">Cargando…</div>
      </div>

      <div v-if="playlists.length === 0 && !loading" class="text-white/70">
        No hay resultados aún. Tocá “Actualizar mood”.
      </div>

      <div class="grid sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5">
        <div v-for="pl in playlists" :key="pl.id"
          class="group rounded-2xl overflow-hidden bg-white/5 border border-white/10 hover:border-white/25 transition cursor-pointer"
          @click="openEmbed(pl.id)">
          <div class="aspect-square overflow-hidden">
            <img :src="pl.image" :alt="pl.name" class="w-full h-full object-cover group-hover:scale-105 transition"
              @error="$event.target.src = FALLBACK_COVER" />
          </div>
          <div class="p-4">
            <div class="font-semibold truncate">{{ pl.name }}</div>
            <div class="text-sm text-white/60 truncate">by {{ pl.owner || 'Spotify' }}</div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>
