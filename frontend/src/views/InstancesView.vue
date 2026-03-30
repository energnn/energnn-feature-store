<template>
  <v-container class="pa-4" fluid>
    <v-card>
      <ProjectSelector
        title="Instances"
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
        <v-text-field
          v-model="filterConfig"
          label="Filter Config"
          variant="outlined"
          clearable
          hide-details
          class="filter-input config"
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

        <v-btn text height="56" @click="openAdvanced">Advanced Filters</v-btn>
        <AdvancedFiltersDialog
          v-model="advDialogVisible"
          :initialTagFilters="savedTagFilters"
          :initialDateFilters="savedDateFilters"
          @save="onAdvSave"
          @cancel="onAdvCancel"
        />

        <v-spacer />

        <v-btn
          color="green"
          class="filter-btn"
          height="56"
          @click="applyFilters"
        >
        Apply
      </v-btn>

        <v-btn
          class="filter-btn"
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

        <!-- Compteur : affichage filtré / total -->
        <v-row class="mb-2" align="center">
          <v-col cols="12" class="d-flex align-center">
            <div>
              <v-chip small class="me-2" outlined>
                <span v-if="isLoadingCounts">Chargement...</span>
                <span v-else>
                  Results : <strong>{{ totalItems }}</strong>
                  <!-- <span v-if="totalItems !== null"> / {{ totalItems }}</span> -->
                  <span> instance<span v-if="totalItems > 1">s</span> found</span>
                </span>
              </v-chip>
            </div>
          </v-col>
        </v-row>
        
        <RowDetailsDialog v-model="detailsDialog" :item="selectedDetails" />

        <!-- DATATABLE -->
        <div class="hide-native-footer">
          <v-data-table
            v-if="!loading"
            :items="instances"
            :headers="headers"
            item-key="compositeKey"
            :items-per-page="instances.length"
            class="elevation-1"
            dense
          >
            <template #item.filter_tags="{ item }">
              <TagChips :tags="item.filter_tags" />
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
                No instances found for project <strong>{{ projectName }}</strong>
              </div>
            </template>

            <!-- PAGINATION CONTROLS -->
            <template #body.append>
              <tr>
                <td :colspan="headers.length" class="pa-4">
                  <div class="d-flex justify-end align-center footer-controls" style="gap:12px;">

                    <!-- input pour page size -->
                    <div class="d-flex align-center page-size-wrapper">
                      <span class="page-size-text">Items per page:</span>
                      <v-text-field
                        v-model.number="pageSize"
                        @keyup.enter="onPageSizeEnter"
                        dense
                        hide-details
                        type="number"
                        :min="1"
                        :max="1000"
                        class="page-size-input"
                        aria-label="Items per page"
                        placeholder=""
                      />
                    </div>
                    
                    <v-pagination
                      v-if="totalPages !== null"
                      v-model="page"
                      :length="totalPages"
                      :total-visible="7"
                      @update:model-value="onPageChange"
                    />
                    <div v-else class="d-flex gap-2 align-center">
                      <v-btn :disabled="pageLocal <= 1" @click="goPrev">Previous</v-btn>
                      <v-btn :disabled="!hasMore" @click="goNext">Next</v-btn>
                    </div>
                  </div>
                </td>
              </tr>
            </template>
          </v-data-table>
        </div>
      </v-card-text>
    </v-card>
  </v-container>

  <!-- DELETE CONFIRM DIALOG -->
  <DeleteConfirmDialog
    v-model="dialog"
    :item="selected"
    entityLabel="instance"
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
import AdvancedFiltersDialog from "@/components/AdvancedFiltersDialog.vue";
import { itemToValue, parseApiErrorForDelete } from "@/utils/formatters";

const PAGE_SIZE = 50;
const store = useStore();

const projectName = ref("");

// pageSize local (changeable by the user)
const pageSize = ref(PAGE_SIZE);

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

// for details dialog
const detailsDialog = ref(false);
const selectedDetails = ref(null);

function openDetails(item) {
  selectedDetails.value = item;
  detailsDialog.value = true;
}

// advanced filters
const advDialogVisible = ref(false);
const savedTagFilters = ref({});
const savedDateFilters = ref({});

function openAdvanced() {
  advDialogVisible.value = true;
}

function onAdvSave(payload) {
  savedTagFilters.value = payload.tagFilters || {};
  savedDateFilters.value = payload.dateFilters || {};
}

function onAdvCancel() {
  savedTagFilters.value = {};
  savedDateFilters.value = {};
  advDialogVisible.value = false;
}

// store-driven state
const loading = computed(() => store.getters.loading);
const pagination = computed(() => store.getters.pagination || { page: 1, limit: PAGE_SIZE, offset: 0, total_count: null, hasMore: false });
if (pagination.value && pagination.value.limit) {
  pageSize.value = pagination.value.limit;
}

// Instances come from the store; we enrich them for display
const instances = computed(() => {
  const arr = store.getters.instances || [];
  return arr.map(i => ({ ...i, compositeKey: `${i.project_name}__${i.name}__${i.config_id}__${i.code_version}` }));
});

// pagination derived values (totalItems, totalPages, hasMore)
const totalItems = computed(() => {
  const t = pagination.value.total_count;
  return (typeof t === "number") ? t : null;
});
const totalPages = computed(() => {
  if (totalItems.value === null) return null;
  return Math.max(1, Math.ceil(totalItems.value / pagination.value.limit));
});
const hasMore = computed(() => pagination.value.hasMore === true);

// page is a computed with setter so v-pagination v-model works and triggers fetch
const page = computed({
  get() {
    return pagination.value.page || 1;
  },
  async set(v) {
    // user changed page via v-pagination; call store to fetch that page (no count)
    await onPageChange(v);
  }
});
// for direct button disabling
const pageLocal = computed(() => pagination.value.page || 1);

// List of projects for this tab
const projectList = computed(() => store.getters.projectsByTable.instances || []);

// ---- local filters ----
const filterName = ref("");
const filterConfig = ref("");
const filterVersionOp = ref(">=");
const filterVersionValue = ref(null);
const versionOps = ["=", ">=", ">", "<=", "<"];

const headers = [
  { title: "Project", value: "project_name" },
  { title: "Name", value: "name" },
  { title: "Config", value: "config_id" },
  { title: "Version", value: "code_version" },
  { title: "Storage ID", value: "storage_path" },
  { title: "Tags", value: "filter_tags", sortable: false },
  { title: "Actions", value: "actions", sortable: false },
];

// small computed
const pageItemsCount = computed(() => instances.value.length);
const isLoadingCounts = computed(() => loading.value);

function buildFilters() {
  const filters = {};
  if (filterName.value) filters.name_like = filterName.value;
  if (filterConfig.value) filters.config_id = filterConfig.value;
  if (filterVersionValue.value !== null && filterVersionValue.value !== "") {
    const v = Number(filterVersionValue.value);
    switch (filterVersionOp.value) {
      case "=":
        filters.version = v;
        break;
      case ">=":
        filters.min_version = v;
        break;
      case ">":
        filters.min_version = v + 1;
        break;
      case "<=":
        filters.max_version = v;
        break;
      case "<":
        filters.max_version = v - 1;
        break;
    }
  }
  if (Object.keys(savedTagFilters.value || {}).length > 0) {
    filters.tag_filters = savedTagFilters.value;
  }

  if (Object.keys(savedDateFilters.value || {}).length > 0) {
    filters.date_filters = savedDateFilters.value;
  }
  console.log("filters : ", filters)
  return filters;
}

function itemToObjectKey(item) {
  return `${item.project_name}/instances/${item.storage_path}`;
}

function isDownloading(item) {
  const key = itemToObjectKey(item);
  return store.getters.isDownloading(key);
}

async function handleDownload(item) {
  const payload = {
    project_name: item.project_name,
    kind: "instances",
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

async function loadPageFromStore(pageNumber = 1, requestCount = false, limit = null) {
  if (!projectName.value) {
    // clear store/state
    await store.dispatch("clearInstances");
    return;
  }
  try {
    // forward limit if provided, otherwise let store use its default/pagination.limit
    await store.dispatch("fetchInstancesPage", {
      project_name: projectName.value,
      pageNumber,
      requestCount,
      filters: buildFilters(),
      limit: limit ?? pageSize.value
    });
  } catch (err) {
    // put a deleteAlert (floating) on fetch error
    const msg = err?.response?.data?.message || err?.message || String(err);
    showDeleteAlert(`Fetch failed: ${msg}`, "error", 0);
  }
}

// apply filters (request count)
async function applyFilters() {
  await loadPageFromStore(1, true);
}

// clear filters and reload first page (request count)
async function clearFilters() {
  filterName.value = "";
  filterConfig.value = null;
  filterVersionOp.value = ">=";
  filterVersionValue.value = null;
  savedTagFilters.value = {};
  savedDateFilters.value = {};
  await loadPageFromStore(1, true);
}

// pagination callbacks
async function onPageChange(newPage) {
  // do not request count on page change
  await loadPageFromStore(newPage, false, pageSize.value);
}

// Handler to press ENTER in the pageSize field
async function onPageSizeEnter() {
  // validation
  let v = Number(pageSize.value) || DEFAULT_PAGE_SIZE;
  if (!Number.isInteger(v) || v <= 0) v = DEFAULT_PAGE_SIZE;
  if (v > 1000) v = 1000; // max clamp on client side (align with server max_limit if necessary)
  pageSize.value = v;

  // ressend the query on page 1 by requesting the count to recalculate totalPages
  await loadPageFromStore(1, true, pageSize.value);
}

function goPrev() {
  const cur = pagination.value.page || 1;
  if (cur > 1) onPageChange(cur - 1);
}
function goNext() {
  if (pagination.value.hasMore) {
    const cur = pagination.value.page || 1;
    onPageChange(cur + 1);
  }
}

// DELETION FUNCTIONS (Currently disabled)
// deletion flow: use store action and reload current page

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
    await store.dispatch("removeInstance", {
      project_name: selected.value.project_name,
      name: selected.value.name,
      config_id: selected.value.config_id,
      code_version: selected.value.code_version
    });
    showDeleteAlert("Instance deleted.", "success", 3500);
    // reload current page (no count)
    const curPage = pagination.value.page || 1;
    await loadPageFromStore(curPage, false);
    closeDialog();
  } catch (err) {
    const friendly = parseApiErrorForDelete(err);
    showDeleteAlert(friendly, "error", 0);
    closeDialog();
  } finally {
    deleting.value = false;
  }
}

// auto-selection flag
const autoSelected = ref(false);

watch(projectList, (newList) => {
  if (!autoSelected.value && (!projectName.value || projectName.value === "") && Array.isArray(newList) && newList.length > 0) {
    projectName.value = itemToValue(newList[0]);
    autoSelected.value = true;
  }
});

watch(projectName, async (nv) => {
  if (nv) {
    hideDeleteAlert();
    // clear store-side instances before new load
    await store.dispatch("clearInstances");
    await clearFilters();
  } else {
    await store.dispatch("clearInstances");
  }
});

onMounted(async () => {
  const current = store.getters.projectsByTable && store.getters.projectsByTable.instances;
  if (!Array.isArray(current) || current.length === 0) {
    await store.dispatch("loadProjects");
  } else if ((!projectName.value || projectName.value === "") && current.length > 0 && !autoSelected.value) {
    projectName.value = itemToValue(current[0]);
    autoSelected.value = true;
    // projectName watcher will trigger fetch
  }
});
</script >

<style scoped>
pre { font-size: 12px; margin: 0; }

/* only hides the footer of tables inside .hide-native-footer */
.hide-native-footer :deep(.v-data-table__footer),
.hide-native-footer :deep(.v-data-table-footer),
.hide-native-footer :deep(.v-datatable__footer) {
  display: none !important;
}

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
.filter-input.name    { width: 380px; }
.filter-input.config  { width: 300px; }
.filter-input.op      { width: 96px;  text-align: center; }
.filter-input.version { width: 140px; }

/* Uniform heights for Vuetify fields */
:deep(.filters-row .v-field) { min-height: 56px; }
:deep(.filters-row .v-input) { --v-input-control-height: 56px; }

/* filter Bouton */
.filter-btn {
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

/* compact page size control */
.page-size-wrapper {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-right: 8px;
}

/* text before the field */
.page-size-text {
  font-size: 0.875rem; /* smaller than main text */
  color: var(--v-theme-on-surface, rgba(0,0,0,0.87));
  white-space: nowrap;
}

/* compact width for input */
.page-size-input {
  max-width: 80px;
  width: 80px;
}

/* adjusting height of the field (Vuetify internals) */
:deep(.page-size-input .v-field) {
  min-height: 36px;
  --v-input-control-height: 36px;
}

/* align the whole footer to the right */
.footer-controls {
  width: 100%;
  justify-content: flex-end;
  align-items: center;
}
</style>