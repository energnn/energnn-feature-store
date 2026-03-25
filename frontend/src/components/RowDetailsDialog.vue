<template>
  <v-dialog v-model="model" max-width="900">
    <v-card>
      <v-card-title class="d-flex justify-space-between align-center">
        <div>
          <span class="text-h6">Row details</span>
          <div v-if="item" class="text-subtitle-2 grey--text ms-4">
            {{ item.project_name ? item.project_name + ' / ' : '' }}{{ item.name ?? item.config_id ?? item.run_id + ' / ' + item.training_step ?? '' }}
          </div>
        </div>

        <div>
          <v-btn icon small @click="copyToClipboard" :title="'Copy JSON'">
            <v-icon>mdi-content-copy</v-icon>
          </v-btn>
          <v-btn icon small @click="close" :title="'Close'">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </div>
      </v-card-title>

      <v-divider />

      <v-card-text>
        <div v-if="!item" class="pa-4">
          No row selected.
        </div>

        <div v-else>
          <v-alert
            v-if="copied"
            type="success"
            dense
            class="mb-3"
            :value="true"
          >
            JSON copied to clipboard.
          </v-alert>

          <pre class="row-json">{{ pretty }}</pre>
        </div>
      </v-card-text>

      <v-divider />

      <v-card-actions>
        <v-spacer />
        <v-btn text @click="close">Close</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { computed, ref } from "vue";

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  item: { type: Object, default: null },
  compact: { type: Boolean, default: false }
});

const emit = defineEmits(["update:modelValue"]);

const model = computed({
  get: () => props.modelValue,
  set: (v) => emit("update:modelValue", v)
});

const copied = ref(false);
let copyTimeout = null;

// pretty JSON
const pretty = computed(() => {
  if (!props.item) return "";
  try {
    if (typeof props.item === "object" && !Array.isArray(props.item)) {
      const { compositeKey, ...rest } = props.item;
      return JSON.stringify(rest, null, props.compact ? 0 : 2);
    }
    return JSON.stringify(props.item, null, props.compact ? 0 : 2);
  } catch (e) {
    return String(props.item);
  }
});

// copy function: tries navigator.clipboard, fallback to textarea
async function copyToClipboard() {
  const text = pretty.value || "";
  try {
    if (navigator && navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text);
    } else {
      // fallback: textarea trick
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
    copied.value = true;
    if (copyTimeout) clearTimeout(copyTimeout);
    copyTimeout = setTimeout(() => (copied.value = false), 2500);
  } catch (e) {
    // ignore - no show
    console.error("copy failed", e);
  }
}

function close() {
  model.value = false;
}
</script>

<style scoped>
.row-json {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, "Roboto Mono", "Courier New", monospace;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 60vh;
  overflow: auto;
  background: var(--v-theme-surface, #f7f7f9);
  color: var(--v-theme-on-surface, #111827);
  padding: 12px;
  border-radius: 6px;
  border: 1px solid var(--v-theme-outline, rgba(0,0,0,0.06));
  /* small elevation for contrast */
  box-shadow: 0 1px 2px rgba(0,0,0,0.04);
  line-height: 1.4;
  font-size: 13px;
}

/* Optional: improve readability on very small screens */
@media (max-width: 600px) {
  .row-json { font-size: 12px; max-height: 50vh; padding: 10px; }
}
</style>
