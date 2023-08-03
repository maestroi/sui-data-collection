<template>
  <div class="app">
    <Header />
    <div class="content">
      <PriceCharts />
    </div>
    <Footer :version="version" />
  </div>
</template>

<script setup>
import { ref } from 'vue';
import PriceCharts from './components/PriceCharts.vue';
import Header from './components/Header.vue';
import Footer from './components/Footer.vue';

const version = ref('0.0.1');
</script>
<style>

html, body {
  width: 100%;
  height: 100%;
  margin: 0;
  padding: 0;
  flex: auto;
  display: block;
}

.app {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  width: 100%; /* Add this line */
  max-width: 90%;
}


.content {
  flex-grow: 1;
  padding: 20px;
  padding-top: 2%; /* Adjust this value based on the height of your header */
  padding-bottom: 60px; /* Adjust this value based on the height of your footer */
  /* Other styles remain the same */
}
</style>
