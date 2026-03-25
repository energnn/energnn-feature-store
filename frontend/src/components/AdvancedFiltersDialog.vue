<template>
  <v-dialog v-model="visibleLocal" max-width="880">
    <v-card>
      <v-card-title class="d-flex justify-space-between align-center">
        <div class="text-h6">Advanced filters</div>
        <div>
          <v-btn icon @click="onCancel" :title="'Cancel'"><v-icon>mdi-close</v-icon></v-btn>
        </div>
      </v-card-title>

      <v-divider />

      <v-card-text>
        <!-- TAGS -->
        <div class="mb-4">
          <div class="d-flex justify-space-between align-center mb-2">
            <div class="text-subtitle-1">Tags</div>
            <v-btn small text @click="addTag"><v-icon left>mdi-plus</v-icon> Add</v-btn>
          </div>

          <div v-if="tags.length === 0" class="mb-2 grey--text text--darken-1">No tags defined.</div>

          <div v-for="(t, idx) in tags" :key="'tag-'+idx" class="d-flex gap-2 align-center mb-2">
            <v-text-field
              v-model="t.key"
              label="Key"
              hide-details
              dense
              class="flex-grow-1"
            />
            <v-text-field
              v-model="t.value"
              label="Value"
              hide-details
              dense
              class="flex-grow-2"
            />
            <v-btn icon small @click="removeTag(idx)" :title="'Remove'">
              <v-icon>mdi-close</v-icon>
            </v-btn>
          </div>
        </div>

        <v-divider class="my-4" />

        <!-- DATES -->
        <div>
          <div class="d-flex justify-space-between align-center mb-2">
            <div class="text-subtitle-1">Date ranges</div>
            <v-btn small text @click="addDate"><v-icon left>mdi-plus</v-icon> Add</v-btn>
          </div>

          <div v-if="dates.length === 0" class="mb-2 grey--text text--darken-1">No date range defined.</div>

          <div v-for="(d, idx) in dates" :key="'date-'+idx" class="d-flex gap-2 align-center mb-2">
            <v-text-field
              v-model="d.key"
              label="Key"
              hide-details
              dense
              class="flex-grow-1"
            />
            
            <v-text-field
              v-model="d.from"
              label="From"
              type="datetime-local"
              hide-details
              dense
              class="flex-grow-1"
            />
            <v-text-field
              v-model="d.to"
              label="To"
              type="datetime-local"
              hide-details
              dense
              class="flex-grow-1"
            />
            <v-btn icon small @click="removeDate(idx)" :title="'Remove'">
              <v-icon>mdi-close</v-icon>
            </v-btn>
          </div>
        </div>
      </v-card-text>

      <v-divider />

      <v-card-actions>
        <v-spacer />
        <v-btn text @click="onCancel">Cancel</v-btn>
        <v-btn color="primary" @click="onSave">Save</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, watch } from "vue";

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  initialTagFilters: { type: Object, default: () => ({}) },      // { key: value, ... }
  initialDateFilters: { type: Object, default: () => ({}) }      // { key: [fromISO, toISO], ... }
});

const emit = defineEmits(["update:modelValue", "save", "cancel"]);

// local visible so we can manage close
const visibleLocal = ref(props.modelValue);

watch(() => props.modelValue, (v) => { visibleLocal.value = v; });

watch(visibleLocal, (v) => emit("update:modelValue", v));

// Initialize local arrays from initial props
function objToTagArr(obj) {
  return Object.entries(obj || {}).map(([k, v]) => ({ key: k, value: v }));
}
function objToDateArr(obj) {
  return Object.entries(obj || {}).map(([k, v]) => ({
    key: k,
    from: Array.isArray(v) && v[0] ? isoToLocalDatetimeInput(v[0]) : "",
    to: Array.isArray(v) && v[1] ? isoToLocalDatetimeInput(v[1]) : ""
  }));
}

function isoToLocalDatetimeInput(iso) {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    const off = d.getTimezoneOffset();
    // create local iso without seconds
    const local = new Date(d.getTime() - off * 60 * 1000);
    return local.toISOString().slice(0, 16); // "YYYY-MM-DDTHH:MM"
  } catch {
    return "";
  }
}

function localDatetimeInputToIso(v) {
  if (!v) return null;
  // v like "2025-09-01T13:45"
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return null;
  return d.toISOString();
}

const tags = ref(objToTagArr(props.initialTagFilters));
const dates = ref(objToDateArr(props.initialDateFilters));

// Reset local arrays whenever initial props change
watch(() => props.initialTagFilters, (nv) => { tags.value = objToTagArr(nv); }, { deep: true });
watch(() => props.initialDateFilters, (nv) => { dates.value = objToDateArr(nv); }, { deep: true });

// Add/remove
function addTag() { tags.value.push({ key: "", value: "" }); }
function removeTag(i) { tags.value.splice(i, 1); }

function addDate() { dates.value.push({ key: "", from: "", to: "" }); }
function removeDate(i) { dates.value.splice(i, 1); }

// Cancel: clear local lines and emit 'cancel' so parent can also clear saved filters if desired
function onCancel() {
  tags.value = [];
  dates.value = [];
  emit("cancel");
  visibleLocal.value = false;
}

// Save: build objects and emit, then close. (DO NOT launch queries here)
function onSave() {
  const tagObj = {};
  for (const t of tags.value) {
    if (t.key && t.key.trim() !== "") {
      tagObj[t.key.trim()] = t.value ?? "";
    }
  }

  const dateObj = {};
  for (const d of dates.value) {
    if (d.key && d.key.trim() !== "") {
      const fromIso = localDatetimeInputToIso(d.from);
      const toIso = localDatetimeInputToIso(d.to);
      // if one side missing, skip or include nulls? we'll include only fully defined ranges
      if (fromIso && toIso) {
        dateObj[d.key.trim()] = [fromIso, toIso];
      }
    }
  }

  emit("save", { tagFilters: tagObj, dateFilters: dateObj });
  visibleLocal.value = false;
}
</script>

<style scoped>
.mb-2 { margin-bottom: 8px; }
.mb-4 { margin-bottom: 16px; }
.gap-2 { gap: 8px; }
.flex-grow-1 { flex: 1 1 0; }
.flex-grow-2 { flex: 2 1 0; }
</style>
