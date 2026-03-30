<template>
  <v-app>
    <!-- TopNav simple -->
    <TopNav />

    <!-- Main content -->
    <v-main>
      <v-container fluid class="pa-4">
        <router-view />
      </v-container>
    </v-main>

    <v-footer padless>
      <v-sheet class="w-100 text-center" color="grey lighten-4" elevation="0" height="48">
        <div class="py-2">© {{ new Date().getFullYear() }} — Feature Store</div>
      </v-sheet>
    </v-footer>
  </v-app>
</template>

<script setup>
import TopNav from "./components/TopNav.vue";
</script>

<style>
.v-application {
  font-family: "Roboto", sans-serif;
}
</style>
