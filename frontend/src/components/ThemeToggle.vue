<template>
  <div class="theme-toggle" role="group" aria-label="Theme toggle">
    <v-btn
      icon
      class="theme-icon-btn"
      :title="iconTitle"
      @click="toggle"
      aria-hidden="false"
      :aria-pressed="isDark"
    >
      <v-icon large>{{ iconName }}</v-icon>
    </v-btn>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useTheme } from "vuetify";

const theme = useTheme();

/* Robust getters/setters for theme name across Vuetify versions */
const getThemeName = () =>
  (theme.global?.name?.value) ??
  (theme.global?.current?.value) ??
  "light";

const setThemeName = (name) => {
  if (theme.global?.name) theme.global.name.value = name;
  else if (theme.global?.current) theme.global.current.value = name;
  try {
    localStorage.setItem("app-theme", name);
  } catch (e) {
    /* ignore storage errors (private browsing, quota, ...)*/
  }
};

const isDark = computed({
  get() {
    return getThemeName() === "dark";
  },
  set(v) {
    setThemeName(v ? "dark" : "light");
  }
});

const iconName = computed(() => (isDark.value ? "mdi-weather-night" : "mdi-white-balance-sunny"));
const iconTitle = computed(() => (isDark.value ? "Basculer en mode clair" : "Basculer en mode sombre"));

function toggle() {
  isDark.value = !isDark.value;
}
</script>

<style scoped>
.theme-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

/* icon button sizing/alignment */
.theme-icon-btn {
  width: 40px;
  height: 40px;
  min-width: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
</style>