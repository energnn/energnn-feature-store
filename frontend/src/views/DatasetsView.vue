<template>
  <v-container class="pa-4" fluid>
    <v-card>
      <ProjectSelector
        title="Datasets"
        v-model="projectName"
        :items="projectList"
      />
      
      <!-- Floating ALERT centered on screen -->
      <FloatingAlert v-model="deleteAlert.show" :message="deleteAlert.message" :type="deleteAlert.type" :autoHideMs="0" />

      <!-- Filter Bar (1 row, horizontal scroll if needed) -->
      <div class="filters-row">
        <v-text-field
          v-model="filterName"
          label="Filter Name"
          variant="outlined"
          clearable
          hide-details
          class="filter-input name"
        />
        <v-select
          v-model="filterSplit"
          :items="splitOptions"
          label="Filter Split"
          variant="outlined"
          clearable
          hide-details
          class="filter-input split"
        />
        <v-select
          v-model="filterVersionOp"
          :items="versionOps"
          label="Op"
          variant="outlined"
          hide-details
          class="filter-input op"
        />
        <v-text-field
          v-model.number="filterVersionValue"
          type="number"
          label="Version"
          variant="outlined"
          hide-details
          class="filter-input version"
        />
        <v-btn
          class="filter-clear-btn"
          color="primary"
          height="56"
          @click="clearFilters"
        >
          Clear
        </v-btn>
      </div>

      <v-divider />

      <v-card-text>
        <v-progress-linear v-if="loading" indeterminate color="primary" class="mb-4" />
        
        <!-- Counter : display filtered / total -->
        <v-row class="mb-2" align="center">
          <v-col cols="12" class="d-flex align-center">
            <div>
              <v-chip small class="me-2" outlined>
                <span v-if="isLoadingCounts">Chargement...</span>
                <span v-else>
                  Results : <strong>{{ filteredCount }}</strong>
                  <!-- <span v-if="totalCount !== filteredCount"> / {{ totalCount }}</span> -->
                  <span> dataset<span v-if="filteredCount > 1">s</span> found</span>
                </span>
              </v-chip>
            </div>
          </v-col>
        </v-row>
        
        <RowDetailsDialog v-model="detailsDialog" :item="selectedDetails" />

        <v-data-table
          v-if="!loading"
          :items="filteredDatasets"
          :headers="headers"
          item-key="compositeKey"
          class="elevation-1"
          dense
        >
          <template #item.tags="{ item }">
            <TagChips :tags="item.tags" />
          </template>

          <template #item.selection_criteria="{ item }">
            <pre class="ma-0" style="white-space: pre-wrap; font-size: 12px;">
              {{ stringify(item.selection_criteria) }}
            </pre>
          </template>

          <template #item.generation_date="{ item }">
            <span>{{ formatDate(item.generation_date) }}</span>
          </template>

          <template #item.actions="{ item }">
            <div class="action-icons">
              <v-icon size="small" @click="openDetails(item)" title="Show row details" >mdi-eye-outline</v-icon>
                <span class="action-icon">
                  <template v-if="isDownloading(item)">
                    <v-progress-circular indeterminate size="18" width="2"></v-progress-circular>
                    <v-btn text small @click="cancel(item)">Cancel</v-btn>
                  </template>
                  <template v-else>
                    <v-icon size="small" title="Download" @click="handleDownload(item)" >mdi-download</v-icon>
                  </template>
                </span>
              <!-- <v-icon size="small" color="error" title="Delete" @click="openDeleteDialog(item)">mdi-delete</v-icon> -->
            </div>
          </template>

          <template #no-data>
            <div class="text-center pa-4">
              No datasets found for project <strong>{{ projectName }}</strong>
            </div>
          </template>
        </v-data-table>
      </v-card-text>
    </v-card>
  </v-container>

  <!-- DELETE CONFIRM DIALOG -->
   <DeleteConfirmDialog
    v-model="dialog"
    :item="selected"
    entityLabel="dataset"
    :loading="deleting"
    @cancel="closeDialog"
    @confirm="handleDelete"
  />
</template>

<script setup>
import { ref, computed, watch, onMounted } from "vue";
import { useStore } from "vuex";
import TagChips from "@/components/TagChips.vue";
import FloatingAlert from '@/components/FloatingAlert.vue'
import DeleteConfirmDialog from '@/components/DeleteConfirmDialog.vue';
import RowDetailsDialog from '@/components/RowDetailsDialog.vue';
import ProjectSelector from '@/components/ProjectSelector.vue';
import { itemToValue, parseApiErrorForDelete } from "@/utils/formatters";

const store = useStore();

const projectName = ref("");

// UI state
const dialog = ref(false);
const selected = ref(null);
const deleting = ref(false);

// local ALERT (for success / error messages)
const deleteAlert = ref({
  show: false,
  type: "success", // "success" | "error" | "info"
  message: "",
  timeoutId: null
});

// pour details dialog
const detailsDialog = ref(false);
const selectedDetails = ref(null);

function openDetails(item) {
  selectedDetails.value = item;
  detailsDialog.value = true;
}

const loading = computed(() => store.getters.loading);

// List of projects for this tab
const projectList = computed(() => store.getters.projectsByTable.datasets || []);

// Distinct split options from the loaded data
const splitOptions = computed(() => {
  const set = new Set((store.getters.datasets || []).map(r => r.split).filter(Boolean));
  return Array.from(set).sort();
});

// ---- local filters ----
const filterName = ref("");
const filterSplit = ref(null);
const filterVersionOp = ref(">=");
const filterVersionValue = ref(null);
const versionOps = ["=", ">=", ">", "<=", "<"];

// computed filteredDatasets (apply client-side filters)
const filteredDatasets = computed(() => {
  let rows = store.getters.datasets || [];

  if (filterName.value) {
    const q = String(filterName.value).toLowerCase();
    rows = rows.filter(r => (r.name || "").toLowerCase().includes(q));
  }
  if (filterSplit.value) {
    rows = rows.filter(r => r.split === filterSplit.value);
  }
  if (filterVersionValue.value !== null && filterVersionValue.value !== "" && !Number.isNaN(Number(filterVersionValue.value))) {
    const v = Number(filterVersionValue.value);
    const op = filterVersionOp.value;
    rows = rows.filter(r => {
      const cv = Number(r.version);
      if (Number.isNaN(cv)) return false;
      switch (op) {
        case "=":  return cv === v;
        case ">=": return cv >= v;
        case ">":  return cv >  v;
        case "<=": return cv <= v;
        case "<":  return cv <  v;
        default:   return true;
      }
    });
  }

  return rows.map(d => ({
    ...d,
    compositeKey: `${d.project_name}__${d.name}__${d.split}__${d.version}`
  }));
});

// baseDatasets = full (unfiltered) array from the store
const baseDatasets = computed(() => store.getters.datasets || []);

// total counter (for the selected project)
const totalCount = computed(() => baseDatasets.value.length);

// filtered counter
const filteredCount = computed(() => filteredDatasets.value.length);

// small state to show "loading" if needed
const isLoadingCounts = computed(() => loading.value);

// auto-selection flag
const autoSelected = ref(false);

// If the project list becomes non-empty and nothing is selected,
// automatically select the first value (only once).
watch(projectList, (newList) => {
  if (!autoSelected.value && (!projectName.value || projectName.value === "") && Array.isArray(newList) && newList.length > 0) {
    projectName.value = itemToValue(newList[0]);
    autoSelected.value = true;
  }
});

const headers = [
  { title: "Project", value: "project_name" },
  { title: "Name", value: "name" },
  { title: "Split", value: "split" },
  { title: "Version", value: "version" },
  { title: "Size", value: "size" },
  { title: "Generation date", value: "generation_date" },
  { title: "Tags", value: "tags", sortable: false },
  { title: "Storage ID", value: "storage_path" },
  { title: "Actions", value: "actions", sortable: false },
];

function stringify(obj) {
  try { return JSON.stringify(obj, null, 2); } catch { return String(obj); }
}
function formatDate(dt) {
  if (!dt) return "";
  // backend may return ISO string; create Date to format
  try {
    const d = new Date(dt);
    return d.toLocaleString();
  } catch {
    return String(dt);
  }
}

// Load configs when projectName changes
watch(projectName, async (newVal) => {
  if (newVal) {
    // clear any previous delete alert when changing project
    hideDeleteAlert();
    clearFilters();
    await store.dispatch("loadDatasets", { project_name: newVal });
  }
});

// Load the project list on mount
onMounted(async () => {
  const current = (store.getters.projectsByTable && store.getters.projectsByTable.datasets) || [];
  if (!Array.isArray(current) || current.length === 0) {
    await store.dispatch("loadProjects");
  } else if ((!projectName.value || projectName.value === "") && current.length > 0) {
    projectName.value = itemToValue(current[0]);
    autoSelected.value = true;
  }
});

function itemToObjectKey(item) {
  return `${item.project_name}/datasets/${item.storage_path}`;
}

function isDownloading(item) {
  const key = itemToObjectKey(item);
  return store.getters.isDownloading(key);
}

async function handleDownload(item) {
  const payload = {
    project_name: item.project_name,
    kind: "datasets",
    storage_path: item.storage_path
  };
  try {
    await store.dispatch("downloadObject", payload);
    showDeleteAlert("Download finished", "success", 2000);
  } catch (err) {
    if (err?.isCanceled) {
      showDeleteAlert("Download cancelled", "info", 1500);
    } else {
      const friendly = err.response.data.message;
      showDeleteAlert(`Download failed: ${friendly}`, "error", 0);
    }
  }
}

function cancel(item) {
  const id = itemToObjectKey(item);
  store.dispatch("cancelDownload", id);
}

// DELETION FUNCTIONS (Currently disabled)

function showDeleteAlert(message, type = "success", autoHideMs = 3500) {
  if (deleteAlert.value.timeoutId) {
    clearTimeout(deleteAlert.value.timeoutId);
    deleteAlert.value.timeoutId = null;
  }
  deleteAlert.value.message = message;
  deleteAlert.value.type = type;
  deleteAlert.value.show = true;

  if (autoHideMs > 0) {
    deleteAlert.value.timeoutId = setTimeout(() => {
      deleteAlert.value.show = false;
      deleteAlert.value.timeoutId = null;
    }, autoHideMs);
  }
}

function hideDeleteAlert() {
  if (deleteAlert.value.timeoutId) {
    clearTimeout(deleteAlert.value.timeoutId);
    deleteAlert.value.timeoutId = null;
  }
  deleteAlert.value.show = false;
  deleteAlert.value.message = "";
}

function openDeleteDialog(item) {
  selected.value = item;
  dialog.value = true;
}

function closeDialog() {
  selected.value = null;
  dialog.value = false;
}

async function handleDelete() {
  if (!selected.value) return;
  deleting.value = true;
  try {
    await store.dispatch("removeDataset", {
      project_name: selected.value.project_name,
      name: selected.value.name,
      split: selected.value.split,
      version: selected.value.version
    });
    showDeleteAlert("Dataset deleted.", "success", 3500);
    closeDialog();
  } catch (err) {
    // custom message depending on the nature of the error
    const friendly = parseApiErrorForDelete(err);
    // display without auto-hide so the user can read it
    showDeleteAlert(friendly, "error", 0);
    // keep the dialog closed (or comment this line to leave it open)
    closeDialog();
  } finally {
    deleting.value = false;
  }
}

// clear filters
function clearFilters() {
  filterName.value = "";
  filterSplit.value = null;
  filterVersionOp.value = ">=";
  filterVersionValue.value = null;
}
</script>

<style scoped>
pre { font-size: 12px; margin: 0; }

/* 1-row container + horizontal scroll if needed */
.filters-row {
  display: flex;
  align-items: center;
  gap: 12px;
  white-space: nowrap;
  overflow-x: auto;    /* if the screen is too small, scroll horizontally */
  padding: 8px 16px;
}

/* Each input stays inline (no wrapping) */
.filters-row > * {
  flex: 0 0 auto;
}

/* Explicit widths */
.filter-input.name    { width: 420px; }
.filter-input.split   { width: 320px; }
.filter-input.op      { width: 96px;  text-align: center; }
.filter-input.version { width: 140px; }

/* Uniform heights for Vuetify fields */
:deep(.filters-row .v-field) { min-height: 56px; }
:deep(.filters-row .v-input) { --v-input-control-height: 56px; }

/* Clear button */
.filter-clear-btn {
  height: 56px;
  align-self: center;
  white-space: nowrap;
}

/* hide horizontal scrollbar but allow scroll*/
.filter-bar::-webkit-scrollbar { height: 8px; }
.filter-bar::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.12); border-radius: 4px; }

.action-icons {
  display: inline-flex;      /* inline-flex évite prise de ligne complète */
  align-items: center;
  gap: 8px;                  /* espace entre les icônes */
}
.action-icon {
  cursor: pointer;
  user-select: none;
}
</style>
