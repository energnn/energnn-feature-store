<template>
    <v-card-title class="d-flex justify-space-between align-center">
      <div>
        <h2 class="ma-0">{{ title }}</h2>
      </div>

      <div style="min-width: 300px; max-width: 400px;">
        <v-select
          v-model="internalValue"
          :items="items"
          :label="label"
          :variant="variant"
        />
      </div>
    </v-card-title>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  modelValue: { type: [String, Number, Object, null], default: '' },
  items: { type: Array, default: () => [] },
  title: { type: String, default: 'Instances' },
  label: { type: String, default: 'Select Project' },
  variant: { type: String, default: 'outlined' },
});

const emit = defineEmits(['update:modelValue']);

const internalValue = computed({
  get() {
    return props.modelValue;
  },
  set(v) {
    emit('update:modelValue', v);
  }
});

</script>

<style scoped>
</style>
