import { createStore } from "vuex";
import * as api from "../services/api";
import { downloadObject as apiDownloadObject } from "../services/api";

const PAGE_SIZE = 15;

const store = createStore({
  state() {
    return {
      instances: [],
      datasets: [],
      configs: [],
      runs: [],
      projectsByTable: { instances: [], configs: [], datasets: [], runs: [] },
      // Pagination state for instances (offset-based)
      pagination: {
        page: 1,
        limit: PAGE_SIZE,
        offset: 0,
        total_count: null, // null => unknown
        hasMore: false
      },
      loading: false,
      error: null,
      downloadingIds: {},
      downloadControllers: {},
    };
  },
  mutations: {
    SET_INSTANCES(state, list) { state.instances = list; },
    REMOVE_INSTANCE(state, key) {
      // key is composite string: `${project_name}__${name}__${config_id}__${code_version}`
      state.instances = state.instances.filter(item => {
        const k = `${item.project_name}__${item.name}__${item.config_id}__${item.code_version}`;
        return k !== key;
      });
    },
    SET_CONFIGS(state, list) { state.configs = list; },
    REMOVE_CONFIG(state, key) {
      state.configs = state.configs.filter(item => {
        const k = `${item.project_name}__${item.config_id}`;
        return k !== key;
      });
    },
    SET_DATASETS(state, list) { state.datasets = list; },
    REMOVE_DATASET(state, key) {
      state.datasets = state.datasets.filter(item => {
        const k = `${item.project_name}__${item.name}__${item.split}__${item.version}`;
        return k !== key;
      });
    },
    SET_PROJECTS_BY_TABLE(state, payload) {
      state.projectsByTable = payload;
    },
    SET_RUNS(state, list) { state.runs = list; },
    REMOVE_RUN(state, key) {
      state.runs = state.runs.filter(item => {
        const k = `${item.project_name}__${item.run_id}__${item.training_step}`;
        return k !== key;
      });
    },

    // loading / error
    SET_LOADING(state, v) { state.loading = v; },
    SET_ERROR(state, e) { state.error = e; },

    // --- Mutations for pagination-driven instances ---
    SET_INSTANCES_PAGE(state, list) { state.instances = list; },
    CLEAR_INSTANCES(state) {
      state.instances = [];
      state.pagination = { page: 1, limit: PAGE_SIZE, offset: 0, total_count: null, hasMore: false };
    },
    SET_PAGINATION(state, { page = null, offset = null, limit = null, total_count = null, hasMore = null } = {}) {
      if (page !== null) state.pagination.page = page;
      if (offset !== null) state.pagination.offset = offset;
      if (limit !== null) state.pagination.limit = limit;
      if (total_count !== null) state.pagination.total_count = total_count;
      if (hasMore !== null) state.pagination.hasMore = hasMore;
    },
    SET_HAS_MORE(state, v) { state.pagination.hasMore = v; },
    SET_DOWNLOADING(state, { id, value }) {
      // Reassign a new reference to trigger responsiveness
      state.downloadingIds = { ...state.downloadingIds, [id]: !!value };
    },

    // --- Mutations for downloading from S3 ---
    REMOVE_DOWNLOADING(state, id) {
      const copy = { ...state.downloadingIds };
      delete copy[id];
      state.downloadingIds = copy;
    },

    SET_DOWNLOAD_CONTROLLER(state, { id, controller }) {
      state.downloadControllers = { ...state.downloadControllers, [id]: controller };
    },

    REMOVE_DOWNLOAD_CONTROLLER(state, id) {
      const copy = { ...state.downloadControllers };
      if (copy[id]) delete copy[id];
      state.downloadControllers = copy;
    },
  },
  actions: {
    async fetchInstancesPage({ commit }, { project_name, pageNumber = 1, requestCount = false, filters = {}, limit=PAGE_SIZE } = {}) {
      commit("SET_LOADING", true);
      commit("SET_ERROR", null);

      // build params for API
      const offset = Math.max(0, (Math.max(1, Number(pageNumber)) - 1) * limit);
      const params = { limit: limit, offset };

      // filters expected keys: name_like, config_id, version, min_version, max_version, etc.
      // copy provided filters into params if present
      if (filters && typeof filters === "object") {
        Object.entries(filters).forEach(([k, v]) => {
          if (v !== undefined && v !== null && v !== "") {
            params[k] = v;
          }
        });
      }

      if (requestCount) {
        params.count = true;
      }

      try {
        const resp = await api.fetchInstancesPage(project_name, params);
        const data = resp && resp.data ? resp.data : {};
        const rawItems = Array.isArray(data.items) ? data.items : [];

        // Ensure project_name is set on each item if backend omitted it
        const items = rawItems.map(i => {
          if (i && (i.project_name === undefined || i.project_name === null)) {
            return { project_name, ...i };
          }
          return i;
        });

        // Commit items
        commit("SET_INSTANCES_PAGE", items);

        // Update pagination: limit & offset guaranteed
        const limit = typeof data.limit === "number" ? data.limit : limit;
        const total_count = (typeof data.total_count === "number") ? data.total_count : null;

        // Compute hasMore:
        let hasMore = false;
        if (total_count !== null) {
          // If we have a total_count, compare
          hasMore = (offset + items.length) < total_count;
        } else {
          // Otherwise, infer from the length of returned items (if it's equal to page limit -> maybe more)
          hasMore = items.length === limit;
        }

        commit("SET_PAGINATION", {
          page: pageNumber,
          offset,
          limit,
          total_count,
          hasMore
        });

        return { items, pagination: { page: pageNumber, offset, limit, total_count, hasMore } };
      } catch (err) {
        commit("SET_ERROR", err);
        console.error("fetchInstancesPage error", err);
        throw err;
      } finally {
        commit("SET_LOADING", false);
      }
    },

    clearInstances({ commit }) {
      commit("CLEAR_INSTANCES");
    },

    async removeInstance({ commit }, { project_name, name, config_id, code_version }) {
      commit("SET_ERROR", null);
      try {
        await api.deleteInstance(project_name, name, config_id, code_version);
        const key = `${project_name}__${name}__${config_id}__${code_version}`;
        commit("REMOVE_INSTANCE", key);
        return true;
      } catch (err) {
        commit("SET_ERROR", err);
        throw err;
      }
    },

    async loadConfigs({ commit }, { project_name }) {
      commit("SET_LOADING", true);
      commit("SET_ERROR", null);
      try {
        const resp = await api.fetchConfigs(project_name);

        // inject project_name when missing in server response
        const configs = (resp.data || []).map(c => {
          if (c && (c.project_name === undefined || c.project_name === null)) {
            return { project_name, ...c };
          }
          return c;
        });

        commit("SET_CONFIGS", configs);
      } catch (err) {
        commit("SET_ERROR", err);
        console.error("loadConfigs error", err);
      } finally {
        commit("SET_LOADING", false);
      }
    },

    async removeConfig({ commit }, { project_name, config_id }) {
      commit("SET_ERROR", null);
      try {
        await api.deleteConfig(project_name, config_id);
        const key = `${project_name}__${config_id}`;
        commit("REMOVE_CONFIG", key);
        return true;
      } catch (err) {
        commit("SET_ERROR", err);
        throw err;
      }
    },
    
    async loadDatasets({ commit }, { project_name }) {
      commit("SET_LOADING", true);
      commit("SET_ERROR", null);
      try {
        const resp = await api.fetchDatasets(project_name);

        // inject project_name when missing in server response
        const datasets = (resp.data || []).map(d => {
          if (d && (d.project_name === undefined || d.project_name === null)) {
            return { project_name, ...d };
          }
          return d;
        });

        commit("SET_DATASETS", datasets);
      } catch (err) {
        commit("SET_ERROR", err);
        console.error("loadDatasets error", err);
      } finally {
        commit("SET_LOADING", false);
      }
    },

    async removeDataset({ commit }, { project_name, name, split, version }) {
      commit("SET_ERROR", null);
      try {
        await api.deleteDataset(project_name, name, split, version);
        const key = `${project_name}__${name}__${split}__${version}`;
        commit("REMOVE_DATASET", key);
        return true;
      } catch (err) {
        commit("SET_ERROR", err);
        throw err;
      }
    },

    async loadRuns({ commit }, { project_name }) {
      commit("SET_LOADING", true);
      commit("SET_ERROR", null);
      try {
        const resp = await api.fetchRuns(project_name);

        // inject project_name when missing in server response
        const runs = (resp.data || []).map(c => {
          if (c && (c.project_name === undefined || c.project_name === null)) {
            return { project_name, ...c };
          }
          return c;
        });

        commit("SET_RUNS", runs);
      } catch (err) {
        commit("SET_ERROR", err);
        console.error("loadRuns error", err);
      } finally {
        commit("SET_LOADING", false);
      }
    },

    async removeRun({ commit }, { project_name, run_id, training_step }) {
      commit("SET_ERROR", null);
      try {
        await api.deleteRun(project_name, run_id, training_step);
        const key = `${project_name}__${run_id}__${training_step}`;
        commit("REMOVE_RUN", key);
        return true;
      } catch (err) {
        commit("SET_ERROR", err);
        throw err;
      }
    },

    async loadProjects({ commit }) {
      commit("SET_LOADING", true);
      commit("SET_ERROR", null);
      try {
        const resp = await api.fetchProjects();
        console.log("loadProjects response:", resp);

        const data = resp && resp.data ? resp.data : null;

        // default payload
        const payload = { instances: [], configs: [], datasets: [], runs: [] };

        if (Array.isArray(data)) {
          // backend returns a list of project_names -> we fill in all the tables
          payload.instances = payload.configs = payload.datasets = data;
        } else if (data && typeof data === "object") {
          // backend returns { instances: [...], configs: [...], datasets: [...] }
          payload.instances = Array.isArray(data.instances) ? data.instances : [];
          payload.configs = Array.isArray(data.configs) ? data.configs : [];
          payload.datasets = Array.isArray(data.datasets) ? data.datasets : [];
          payload.runs = Array.isArray(data.runs) ? data.runs : [];
          // case where backend would return "instances": null -> tables remain empty
        } else {
          console.warn("loadProjects: unexpected response format", data);
        }

        commit("SET_PROJECTS_BY_TABLE", payload);
        console.log("projectsByTable set to:", payload);
      } catch (err) {
        commit("SET_ERROR", err);
        console.error("loadProjects error", err);
      } finally {
        commit("SET_LOADING", false);
      }
    },

    async downloadObject({ commit }, payload) {

      // build object_key
      let object_key;
      if (typeof payload === "string") {
        object_key = payload;
      } else {
        const { project_name, kind, storage_path} = payload;
        if (!project_name || !kind || !storage_path) {
          throw new Error("downloadObject: missing parameters");
        }
        object_key = `${project_name}/${kind}/${storage_path}`;
      }
      const id = object_key;

      // create controller
      const controller = new AbortController();

      // save controller in state so cancelDownload can access it
      commit("SET_DOWNLOAD_CONTROLLER", { id, controller });
      commit("SET_DOWNLOADING", { id, value: true });

      try {
        const resp = await apiDownloadObject(object_key, { signal: controller.signal });

        // determine filename from Content-Disposition header (robuste)
        let filename = object_key.split("/").pop() || "download";
        try {
          const cd = resp.headers["content-disposition"] || resp.headers["Content-Disposition"];
          if (cd) {
            const m = /filename\*=UTF-8''([^;]+)|filename="([^"]+)"/i.exec(cd);
            if (m) filename = decodeURIComponent(m[1] || m[2]);
            else {
              const m2 = /filename=([^;]+)/i.exec(cd);
              if (m2) filename = m2[1].replace(/(^"|"$)/g, "");
            }
          }
        } catch (e) {
          console.warn("Could not parse Content-Disposition", e);
        }

        const blob = new Blob([resp.data], { type: resp.headers["content-type"] || "application/octet-stream" });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);

        commit("REMOVE_DOWNLOAD_CONTROLLER", id);
        commit("REMOVE_DOWNLOADING", id);

        return { success: true, object_key: id, filename };
      } catch (err) {
        commit("REMOVE_DOWNLOAD_CONTROLLER", id);
        commit("REMOVE_DOWNLOADING", id);

        // if aborted, throw a specific error so UI can detect cancellation
        if (err && (err.name === "AbortError" || err?.code === "ERR_CANCELED")) {
          const e = new Error("Download aborted by user");
          e.isCanceled = true;
          throw e;
        } 
        let friendly = "Download failed";
        if (err?.response?.data) {
          const data = err.response.data;
          try {
            if (data instanceof Blob) {
              const text = await data.text();
              try {
                const parsed = JSON.parse(text);
                if (parsed?.message) {
                  friendly = parsed.message;
                } else {
                  friendly = text || friendly;
                }
              } catch {
                friendly = text || friendly;
              }
            } else if (typeof data === "object") {
              friendly = data.message || data.detail || JSON.stringify(data);
            }
          } catch (parseErr) {
            console.warn("Could not parse error response", parseErr);
          }
        } else if (err?.message) {
          friendly = err.message;
        }

        const e = new Error(friendly);
        e._original = err;
        throw e;
      }
    },
    
    cancelDownload({ commit, state }, id) {
      const controller = state.downloadControllers && state.downloadControllers[id];
      if (controller) {
        try {
          controller.abort();
        } catch (e) {
          console.warn("cancelDownload abort error", e);
        } finally {
          commit("REMOVE_DOWNLOAD_CONTROLLER", id);
          commit("REMOVE_DOWNLOADING", id);
        }
      } else {
        // nothing to cancel
      }
    },

  },
  getters: {
    instances: (s) => s.instances,
    configs: (s) => s.configs,
    datasets: (s) => s.datasets,
    runs: (s) => s.runs,
    projectsByTable: (s) => s.projectsByTable,
    loading: (s) => s.loading,
    error: (s) => s.error,
    pagination: (s) => s.pagination,
    isDownloading: (s) => (id) => !!(s.downloadingIds && s.downloadingIds[id]),
    canCancelDownload: (s) => (id) => !!(s.downloadControllers && s.downloadControllers[id]),
  },
});

export default store;
