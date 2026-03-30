<template>
  <v-container class="pa-4" fluid>
    <v-card>
      <ProjectSelector
        title="Runs"
        v-model="projectName"
        :items="projectList"
      />
      
      <!-- Floating ALERT centered on screen -->
      <FloatingAlert v-model="deleteAlert.show" :message="deleteAlert.message" :type="deleteAlert.type" :autoHideMs="0" />

      <!-- Filter Bar (1 row, horizontal scroll if needed) -->
      <div class="filters-row">
        <v-text-field
          v-model="filterRunId"
          label="Filter Run ID"
          variant="outlined"
          clearable
          hide-details
          class="filter-input run_id"
        />
        <v-text-field
          v-model.number="filterStep"
          type="number"
          label="Training step"
          variant="outlined"
          hide-details
          class="filter-input step"
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
                  <span> run<span v-if="filteredCount > 1">s</span> found</span>
                </span>
              </v-chip>
            </div>
          </v-col>
        </v-row>
        
        <RowDetailsDialog v-model="detailsDialog" :item="selectedDetails" />

        <v-data-table
          v-if="!loading"
          :items="filteredRuns"
          :headers="headers"
          item-key="compositeKey"
          class="elevation-1"
          dense
        >

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
              No runs found for project <strong>{{ projectName }}</strong>
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
    entityLabel="run"
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
const projectList = computed(() => store.getters.projectsByTable.runs || []);

// Distinct split options from the loaded data
const splitOptions = computed(() => {
  const set = new Set((store.getters.runs || []).map(r => r.split).filter(Boolean));
  return Array.from(set).sort();
});

// ---- local filters ----
const filterRunId = ref("");
const filterStep = ref(null);

// computed filteredRuns (apply client-side filters)
const filteredRuns = computed(() => {
  let rows = store.getters.runs || [];

  if (filterRunId.value) {
    const q = String(filterRunId.value).toLowerCase();
    rows = rows.filter(r => (r.run_id || "").toLowerCase().includes(q));
  }
  if (filterStep.value) {
    rows = rows.filter(r => r.training_step === filterStep.value);
  }

  return rows.map(d => ({
    ...d,
    compositeKey: `${d.project_name}__${d.run_id}__${d.training_step}`
  }));
});

// baseRuns = full (unfiltered) array from the store
const baseRuns = computed(() => store.getters.runs || []);

// total counter (for the selected project)
const totalCount = computed(() => baseRuns.value.length);

// filtered counter
const filteredCount = computed(() => filteredRuns.value.length);

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
  { title: "Run ID", value: "run_id" },
  { title: "Training Step", value: "training_step" },
  { title: "Parent Run ID", value: "parent_run_id" },
  // { title: "Best", value: "best" },
  // { title: "Last", value: "last" },
  // { title: "Tags", value: "tags", sortable: false },
  // { title: "Storage ID", value: "storage_path" },
  { title: "Actions", value: "actions", sortable: false },
];

// Load runs when projectName changes
watch(projectName, async (newVal) => {
  if (newVal) {
    // clear any previous delete alert when changing project
    hideDeleteAlert();
    clearFilters();
    await store.dispatch("loadRuns", { project_name: newVal });
  }
});

// Load the project list on mount
onMounted(async () => {
  const current = (store.getters.projectsByTable && store.getters.projectsByTable.runs) || [];
  if (!Array.isArray(current) || current.length === 0) {
    await store.dispatch("loadProjects");
  } else if ((!projectName.value || projectName.value === "") && current.length > 0) {
    projectName.value = itemToValue(current[0]);
    autoSelected.value = true;
  }
});

function itemToObjectKey(item) {
  return `${item.project_name}/runs/${item.run_id}/checkpoints/${item.training_step}`;
}

function isDownloading(item) {
  const key = itemToObjectKey(item);
  return store.getters.isDownloading(key);
}

async function handleDownload(item) {
  const payload = {
    project_name: item.project_name,
    kind: "runs",
    storage_path: `${item.run_id}/checkpoints/${item.training_step}.tar.gz`
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
    await store.dispatch("removeRun", {
      project_name: selected.value.project_name,
      run_id: selected.value.run_id,
      training_step: selected.value.training_step
    });
    showDeleteAlert("Run deleted.", "success", 3500);
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
  filterRunId.value = "";
  filterStep.value = null;
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
.filter-input.run_id    { width: 420px; }
.filter-input.step   { width: 150px; }

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
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.action-icon {
  cursor: pointer;
  user-select: none;
}
</style>
