<template>
    <header class="header">
      <div class="header-text">
        Sui Data
      </div>
      <!-- Add other header elements here -->
    </header>
  </template>

  <script>
  export default {
    name: 'Header',
    // Add your component logic here, if needed
  }
  </script>

  <style>
  /* Add your custom styles for the header and logo here */

  .header-text {
    text-align: center;
    font-size: 20px;
  }

  .header {
    position: fixed;
    left: 0;
    top: 0;
    width: 100%;
    background-color: #121212;
    text-align: left;
    padding: 10px;
  }

  .logo {
    margin-right: 2px;
    /* Add any other styles for the logo here */
  }

  .logo img {
    max-height: 30px; /* Adjust the height as needed */
  }
  </style>
