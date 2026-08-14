<template>
  <AppShell />
</template>

<script setup>
import { onMounted, onUnmounted } from 'vue'
import AppShell from './layouts/AppShell.vue'
import { useWardStore } from './stores/ward.js'

const store = useWardStore()

onMounted(() => {
  store.start()
})

onUnmounted(() => {
  store.stop()
})
</script>
