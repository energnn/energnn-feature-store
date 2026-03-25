<template>
  <v-app-bar color="primary" dark app>
    <div class="d-flex align-center" style="gap:12px;">
      <img :src="logo" alt="EnerGNN" class="app-logo" />
      <v-toolbar-title @click="goHome" style="cursor: pointer;">{{ title }}</v-toolbar-title>
    </div>

    <v-spacer />

    <!-- navigation via router -->
    <v-btn text :to="{ name: 'instances' }">Instances</v-btn>
    <v-btn text :to="{ name: 'datasets' }">Datasets</v-btn>
    <v-btn text :to="{ name: 'configs' }">Configs</v-btn>
    <v-btn text :to="{ name: 'runs' }">Runs</v-btn>
    <ThemeToggle />
  </v-app-bar>
</template>

<script setup>
import { useRouter } from "vue-router";
import ThemeToggle from "@/components/ThemeToggle.vue";
import logo from "@/assets/energnn_logo128_black.png"

const props = defineProps({
  title: { type: String, default: "EnerGNN Feature Store" },
});

const router = useRouter();

function goHome() {
  router.push({ name: "instances" });
}
</script>

<style scoped>
.app-logo {
  height: 36px;
  width: auto;
  display: inline-block;
  margin-left: 8px;
}
.v-application .v-toolbar__title {
  font-weight: 600;
}
</style>
