<template>
    <!-- Variante texto -->
    <button v-if="visible && variant === 'text'" @click="handleInstall" class="px-3 py-2 rounded-lg border border-white/20 hover:border-white/40
           bg-white/5 hover:bg-white/10 text-white text-sm flex items-center gap-2" title="Instalar Mood Music">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M12 3v12m0 0l4-4m-4 4l-4-4M4 21h16" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"
                stroke-linejoin="round" />
        </svg>
        Instalar app
    </button>

    <!-- Variante ícono -->
    <button v-if="visible && variant === 'icon'" @click="handleInstall" class="cursor-pointer h-9 w-9 rounded-full bg-white/10 hover:bg-white/20 hover:scale-105 active:scale-95
       text-white flex items-center justify-center border border-white/15 transition transform"
        :title="isIOS() ? 'Agregar a Inicio (iOS)' : 'Instalar app'" aria-label="Instalar app">
        <!-- ícono “instalar” -->
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M12 3v10m0 0l4-4m-4 4l-4-4M4 21h16" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"
                stroke-linejoin="round" />
        </svg>
    </button>


    <!-- Fallback iOS: guía -->
    <div v-if="showIosGuide" class="fixed inset-0 bg-black/60 grid place-items-center z-50">
        <div class="bg-[#1a1a1e] text-white max-w-sm w-full rounded-2xl p-5 shadow-xl">
            <div class="flex items-center justify-between mb-3">
                <h3 class="font-semibold">Agregar a la pantalla de inicio</h3>
                <button @click="showIosGuide = false" class="text-white/60 hover:text-white">✕</button>
            </div>
            <ol class="space-y-2 text-sm leading-6">
                <li>1) Abrí en <b>Safari</b> y tocá <span class="px-1 py-0.5 rounded bg-white/10">Compartir</span>
                    (flecha ↑).</li>
                <li>2) Elegí <b>“Agregar a Inicio”</b>.</li>
                <li>3) Confirmá <b>Mood Music</b>.</li>
            </ol>
            <p class="text-xs text-white/60 mt-3">iOS no permite el diálogo de instalación programático.</p>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps({
    variant: { type: String, default: 'text' } // 'text' | 'icon'
})

const deferredPrompt = ref(null)
const visible = ref(false)
const showIosGuide = ref(false)

const isStandalone = () => {
    const dm = window.matchMedia('(display-mode: standalone)').matches
    return dm || window.navigator.standalone === true
}
const isIOS = () => /iPhone|iPad|iPod/i.test(navigator.userAgent)

function evaluateVisibility() {
    if (isStandalone()) { visible.value = false; return }
    if (isIOS()) { visible.value = true; return }
    visible.value = !!deferredPrompt.value
}

function handleInstall() {
    if (isIOS()) { showIosGuide.value = true; return }
    if (!deferredPrompt.value) return
    deferredPrompt.value.prompt()
    deferredPrompt.value.userChoice.finally(() => {
        deferredPrompt.value = null
        evaluateVisibility()
    })
}

function onBeforeInstallPrompt(e) {
    e.preventDefault()
    deferredPrompt.value = e
    evaluateVisibility()
}
function onAppInstalled() {
    visible.value = false
    showIosGuide.value = false
    console.log('PWA instalada 🎉')
}

onMounted(() => {
    window.addEventListener('beforeinstallprompt', onBeforeInstallPrompt)
    window.addEventListener('appinstalled', onAppInstalled)
    evaluateVisibility()
})
onBeforeUnmount(() => {
    window.removeEventListener('beforeinstallprompt', onBeforeInstallPrompt)
    window.removeEventListener('appinstalled', onAppInstalled)
})

/* expose for template title binding */
function isIOSExpose() { return isIOS() }
const isIOSRef = isIOSExpose
</script>
