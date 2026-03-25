<template>
  <div class="tags-cell">
    <v-chip
      v-if="!hasTags"
      small
      :color="defaultColor"
      :text-color="textColor"
      class="tag-chip empty"
    >
      —
    </v-chip>

    <template v-else>
      <v-chip
        v-for="({ key, val }) in entries"
        :key="key"
        small
        :color="defaultColor"
        :text-color="textColor"
        :outlined="outlined"
        class="tag-chip"
        :title="key + ': ' + parseValue(val)"
      >
        <span class="tag-key">{{ key }}</span><span class="tag-sep">:</span>&nbsp;<span class="tag-val">{{ parseValue(val) }}</span>
      </v-chip>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  tags: {
    type: [Object, null],
    default: null
  },
  defaultColor: {
    type: String,
    default: 'primary'
  },
  textColor: {
    type: String,
    default: 'white'
  },
  maxWidth: {
    type: [String, Number],
    default: '330px'
  },
  outlined: {
    type: [Boolean],
    default: true
  }
});

const hasTags = computed(() => {
  return props.tags && Object.keys(props.tags).length > 0;
});

const entries = computed(() => {
  if (!props.tags) return [];
  // preserve insertion order of object keys
  return Object.keys(props.tags).map(k => ({ key: k, val: props.tags[k] }));
});

function parseValue(v) {
  if (v === null || v === undefined) return String(v);
  if (typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean') {
    const s = String(v);
    return s.length > 40 ? s.slice(0, 37) + '...' : s;
  }
  try {
    const s = JSON.stringify(v);
    return s.length > 40 ? s.slice(0, 37) + '...' : s;
  } catch {
    return String(v);
  }
}
</script>

<style scoped>
.tags-cell {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 10px;
  align-items: flex-start;
  align-content: flex-start;
  max-width: 100%;
  padding: 4px 0;
}

.tag-chip {
  max-width: var(--tag-chip-max-width, 330px);
  overflow: hidden;
  text-overflow: ellipsis;
  margin: 0;
}

.tag-chip .v-chip__content {
  padding-left: 8px;
  padding-right: 8px;
}

.tag-key { font-weight: 600; }
.tag-sep { opacity: 0.8; }
.tag-val { opacity: 0.9; }

.tag-chip.empty { color: rgba(0,0,0,0.6); border-style: dashed; }
</style>
