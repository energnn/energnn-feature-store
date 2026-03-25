<template>
  <div v-if="visible" class="floating-alert" role="alert" aria-live="assertive">
    <v-alert :type="type" prominent elevation="6" class="ma-0">
      <div class="floating-alert-content">
        <div class="msg">{{ message }}</div>
        <div class="actions">
          <v-btn text small class="close-btn" @click="close">Close</v-btn>
        </div>
      </div>
    </v-alert>
  </div>
</template>

<script setup>
import { ref, watch, onBeforeUnmount } from 'vue';

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  type: { type: String, default: 'info' },
  message: { type: String, default: '' },
  autoHideMs: { type: Number, default: 3500 }
});

const emit = defineEmits(['update:modelValue', 'close']);

const visible = ref(props.modelValue);
let timeoutId = null;

watch(() => props.modelValue, (v) => {
  visible.value = v;
  setupAutoHide();
});

watch(() => props.message, () => {
  // if message changes while visible, reset auto-hide
  setupAutoHide();
});

function setupAutoHide() {
  if (timeoutId) {
    clearTimeout(timeoutId);
    timeoutId = null;
  }
  if (visible.value && props.autoHideMs && props.autoHideMs > 0) {
    timeoutId = setTimeout(() => {
      close();
    }, props.autoHideMs);
  }
}

function close() {
  visible.value = false;
  emit('update:modelValue', false);
  emit('close');
  if (timeoutId) {
    clearTimeout(timeoutId);
    timeoutId = null;
  }
}

onBeforeUnmount(() => {
  if (timeoutId) clearTimeout(timeoutId);
});
</script>

<style scoped>
.floating-alert {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 9999;
  width: min(90%, 760px);
  pointer-events: auto;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 0 12px;
}
.floating-alert .floating-alert-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  width: 100%;
}
.floating-alert .floating-alert-content .msg { flex: 1 1 auto; white-space: pre-wrap; word-break: break-word; font-size: 14px; }
.floating-alert .actions { flex: 0 0 auto; }
.close-btn {
  background: white !important;
  color: black !important;
  border: 1px solid rgba(0,0,0,0.12);
  min-width: 64px;
  padding: 6px 12px;
  border-radius: 4px;
  box-shadow: none !important;
}
</style>
