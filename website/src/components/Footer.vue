<template>
    <footer class="footer">
      <p>Version: {{ version }}</p>
    </footer>
  </template>

  <script setup>

  // Accept version as a prop
  const { version } = defineProps(['version']);
  </script>

  <style>
  .footer {
    position: fixed;
    left: 0;
    bottom: 0;
    width: 100%;
    background-color: #121212;
    text-align: left;
    padding: 10px;
  }
  </style>
