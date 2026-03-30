<template>
  <v-dialog v-model="visible" max-width="520" persistent>
    <v-card>
      <v-card-title class="text-h6">{{ title }}</v-card-title>

      <v-card-text>
        <div v-if="item">
          <slot name="message">
            Are you sure you want to delete {{ entityLabel }}
            <span v-if="itemLabel"> <strong>{{ itemLabel }}</strong></span>
            <span v-if="details"> ({{ details }})</span>
            ?
          </slot>
        </div>
      </v-card-text>

      <v-card-actions>
        <v-spacer />
        <v-btn text @click="onCancel">Cancel</v-btn>
        <v-btn :loading="loading" color="error" depressed @click="onConfirm">{{ positiveText }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { computed, watch } from 'vue';

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  entityLabel: { type: String, default: 'item' },
  item: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  positiveText: { type: String, default: 'Delete' },
  title: { type: String, default: 'Confirm deletion' }
});

const emit = defineEmits(['update:modelValue', 'confirm', 'cancel']);

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v)
});

// build simple item label and details for display
const itemLabel = computed(() => {
  if (!props.item) return null;
  // try common identifying keys
  const i = props.item;
  return i.project_name ? `${i.project_name}/${i.name ?? i.config_id ?? i.id ?? ''}` : (i.name || i.config_id || i.id || null);
});
const details = computed(() => {
  if (!props.item) return null;
  // add extra short details like version/split
  const i = props.item;
  const parts = [];
  if (i.config_id && i.name) parts.push(`config ${i.config_id}`);
  if (i.code_version !== undefined && i.code_version !== null) parts.push(`v${i.code_version}`);
  if (i.split) parts.push(`split ${i.split}`);
  if (i.version !== undefined && i.version !== null && i.code_version === undefined) parts.push(`v${i.version}`);
  return parts.length ? parts.join(', ') : null;
});

function onConfirm() {
  emit('confirm');
}
function onCancel() {
  emit('cancel');
}

watch(() => props.modelValue, (v) => {
  if (!v) emit('close');
});
</script>

<style scoped>
/* ensure buttons look consistent */
.v-card-title { padding-bottom: 4px; }
.v-card-text { padding-top: 4px; }
</style>
