import "./styles/global.css";
import { createApp } from "vue";
import App from "./App.vue";
import router from "./router";
import store from "./store";

// Vuetify - using the factory in src/plugins/vuetify.js
import "vuetify/styles";
import createMyVuetify from "./plugins/vuetify";

// Material Design Icons (font)
import "@mdi/font/css/materialdesignicons.css";

/**
 * Retrieves the theme preference:
 * - prioritizes the value persisted in localStorage ('app-theme' = 'light'|'dark')
 * - otherwise, detects the system preference via matchMedia
 */
function detectInitialTheme() {
  const stored = localStorage.getItem("app-theme");
  if (stored === "dark" || stored === "light") return stored;

  // fallback to system preference
  if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
    return "dark";
  }
  return "light";
}

const defaultTheme = detectInitialTheme();
const vuetify = createMyVuetify({ defaultTheme });

const app = createApp(App);
app.use(router);
app.use(store);
app.use(vuetify);
app.mount("#app");
