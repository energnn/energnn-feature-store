import { createRouter, createWebHistory } from "vue-router";
import InstancesView from "../views/InstancesView.vue";
import DatasetsView from "../views/DatasetsView.vue";
import ConfigsView from "../views/ConfigsView.vue";
import RunsView from "../views/RunsView.vue";

const routes = [
  { path: "/", redirect: "/instances" },
  { path: "/instances", name: "instances", component: InstancesView },
  { path: "/datasets", name: "datasets", component: DatasetsView },
  { path: "/configs", name: "configs", component: ConfigsView },
  { path: "/runs", name: "runs", component: RunsView },
  // fallback
  { path: "/:catchAll(.*)", redirect: "/instances" }
];

const router = createRouter({
  history: createWebHistory(),
  routes
});

export default router;
