import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000",
  timeout: 10000
});

// Projects List
export async function fetchProjects() {
  return api.get("/projects");
}

// Download from S3
export const downloadObject = (objectKey, { signal } = {}) => {
  return api.get("/download", {
    params: { object_key: objectKey },
    responseType: "blob",
    timeout: 0,
    signal
  });
};

// Instances
export const fetchInstancesPage = (project_name, body = {}) => {
  return api.post("/instances_page/search", body, {
    params: { project_name: project_name }
  });
};

export const deleteInstance = (project_name, name, config_id, code_version) => {
  return api.delete("/instance", {
    params: { project_name, name, config_id, code_version }
  });
};

// Datasets
export const fetchDatasets = (project_name) => api.get("/datasets", { params: { project_name } });
export const deleteDataset = (project_name, name, split, version) => api.delete("/dataset", { params: { project_name, name, split, version } });

// Configs
export const fetchConfigs = (project_name) => api.get("/configs", { params: { project_name } });
export const deleteConfig = (project_name, config_id) => api.delete("/config", { params: { project_name, config_id } });

// Runs
export const fetchRuns = (project_name) => api.get("/runs", { params: { project_name } });
export const deleteRun = (project_name, run_id, training_step) => api.delete("/run", { params: { project_name, run_id, training_step } });

export default api;
