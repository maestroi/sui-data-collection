<template>

  <footer class="footer">
    <div class="footer-content">
      <p class="version-text">Version: {{ version }}</p>
      <a href="https://github.com/maestroi/sui-data-collection" target="_blank" class="github-link">
        <i class="fab fa-github fa-2x"></i>
      </a>
    </div>
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
.version-text {
  font-size: 12px; /* Set the font size to 12px */
}

.footer-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.github-link {
  text-decoration: none;
  color: inherit; /* Use this to maintain the text color */
}
</style>
