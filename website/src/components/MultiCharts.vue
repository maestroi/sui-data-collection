<template>
  <div>
    <div class="selections-container">
      <div class="selection">
        <label for="provider">Validator</label>
        <v-select
          v-model="selectedProviders"
          :options="providers"
          multiple
          class="style-chooser"
          @input="updateChartData"
        ></v-select>
      </div>
      <div class="selection">
        <select v-model="selectedNetwork" @change="updateChartData">
          <option v-for="network in networks" :key="network" :value="network">
            {{ network }}
          </option>
        </select>
      </div>
      <div class="selection">
    <button @click="downloadCSV">Download CSV</button>
  </div>
  </div>
    <div class="charts-container">
      <div class="chart">
        <h2>APY</h2>
        <canvas id="epoch-apy-chart" ref="apyChart"></canvas>
      </div>
      <div class="chart">
        <h2>Stake</h2>
        <canvas id="epoch-stake-chart" ref="stakeChart"></canvas>
      </div>
      <div class="chart">
        <h2>Gas Price</h2>
        <canvas id="epoch-gas-price-chart" ref="gasPriceChart"></canvas>
      </div>
      <div class="chart">
        <h2>Commission Rate</h2>
        <canvas id="epoch-commission-rate-chart" ref="commissionRateChart"></canvas>
      </div>
      <div class="chart">
        <h2>Voting Power</h2>
        <canvas id="epoch-voting-power-chart" ref="votingPowerChart"></canvas>
      </div>
      <div class="chart">
        <h2>APY Change rate</h2>
        <canvas id="epoch-rate-change-chart" ref="changeRateChart"></canvas>
      </div>
    </div>
    <div class="table-div">
        <vue3-datatable
            :rows="tableDataRef"
            :columns="tableColumns"
            :sortable="true"
            :sortColumn="params.sort_column"
            :sortDirection="params.sort_direction"
            :showNumbersCount="3"
            :pageSize="params.pagesize"
            skin="bh-table-compact"
            class="alt-pagination"> </vue3-datatable>
      </div>
  </div>
</template>

<script setup>
import { onMounted, ref, watch, reactive } from 'vue';
import axios from 'axios';
import { Chart, registerables } from 'chart.js';
import Vue3Datatable from "@bhplugin/vue3-datatable";
import vSelect from 'vue-select'
import "@bhplugin/vue3-datatable/dist/style.css";

// Register the necessary plugins
Chart.register(...registerables);

const chartRef = ref(null);
const selectedProviders = ref(['Blockdaemon']);
const selectedNetwork = ref('mainnet');
const gasPriceChart = ref(null);
const apyChart = ref(null);
const commissionRateChart = ref(null);
const votingPowerChart = ref(null);
const changeRateChart = ref(null);
const tableDataRef = ref([]);

let data = [];
const providers = ref([]);
const networks = ['mainnet', 'testnet'];
const baseUrl = 'https://api.sui-data.com/api';


const params = reactive({
        current_page: 1,
        pagesize: 20,
        sort_column: 'epoch',
        sort_direction: 'desc',
    });

const tableColumns = ref([
      { field: "epoch", title: "Epoch" },
      { field: "validatorName", title: "Name" },
      { field: "gasPrice", title: "Gas Price" },
      { field: "apy", title: "APY" },
      { field: "changeRate", title: "APY Change"},
      { field: "commissionRate", title: "Commission Rate" },
      { field: "votingPower", title: "Voting Power" },
      { field: "stakeAmount", title: "Stake Amount" },
    ]);


const fetchData = async () => {
  try {
    const response = await axios.get(`${baseUrl}/data?network=${selectedNetwork.value}`);
    data = response.data;
    providers.value = getUniqueProviders();
    updateChartData();
    updateTable();
  } catch (error) {
    console.error('Failed to fetch data:', error);
  }
};

const updateTable = () => {
  // Filter data based on selected provider and network
  const filteredData = data.filter((item) =>
    selectedProviders.value.includes(item.name) &&
    selectedNetwork.value.includes(item.network)
  );

  // Extract the required data
  const tableData = filteredData.map((item) => ({
    epoch: item.epoch,
    validatorName: item.name,
    gasPrice: item.gas_price,
    apy: (item.apy * 100).toFixed(4) + '%',
    changeRate: (item.rate_change * 100).toFixed(4) + '%',
    commissionRate: item.commission_rate / 100 + '%',
    votingPower: item.voting_power,
    stakeAmount: (item.stake / 1000000000).toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }),
  }));

  // Assuming you have a reactive reference to store the table data
  tableDataRef.value = tableData;
};

const downloadCSV = async () => {
  try {
    // Build the names query parameter
    const namesParam = selectedProviders.value.map(name => `names=${encodeURIComponent(name)}`).join('&');

    const url = `${baseUrl}/csv?${namesParam}&network=${encodeURIComponent(selectedNetwork.value)}`;

    const response = await axios.get(url, { responseType: 'blob' });
    const blob = new Blob([response.data], { type: 'text/csv;charset=utf-8' });
    const link = document.createElement('a');
    link.href = window.URL.createObjectURL(blob);

    // Create a filename based on the selected providers and network
    const providers = selectedProviders.value.join('_');
    const networkSuffix = selectedNetwork.value === 'mainnet' ? '-mainnet' : '-testnet';
    link.download = `${providers}${networkSuffix}.csv`;

    link.click();
    window.URL.revokeObjectURL(link.href);
  } catch (error) {
    console.error('Failed to download CSV:', error);
  }
};


const getUniqueProviders = () => {
  const uniqueProviders = Array.from(new Set(data.map((item) => item.name)));
  return uniqueProviders.sort();
};

const chartInstances = {
  gasPrice: null,
  apy: null,
  commissionRate: null,
  votingPower: null,
};

// Update the initializeChart function to accept the chart's name
const initializeChart = (chartName, labels, datasets) => {
  const canvas = document.getElementById(chartName);
  if (canvas) {
    const ctx = canvas.getContext('2d');
    return new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: datasets,
      },
      options: {
        responsive: true,
        scales: {
          x: {
            type: 'linear',
            position: 'bottom',
          },
          y: {
            beginAtZero: false,
          },
        },
      },
    });
  }
  return null;
};


const initializeAndOrUpdateChart = (chartName, epochs, datasets) => {
  let chartInstance = chartInstances[chartName];

  // If the chartInstance does not exist, initialize it
  if (!chartInstance) {
    chartInstance = new Chart(document.getElementById(chartName), {
      type: 'line',
      data: {
        labels: epochs,
        datasets: datasets,
      },
      options: {
        responsive: true,
        scales: {
          x: {
            type: 'linear',
            position: 'bottom',
          },
          y: {
            beginAtZero: false,
          },
        },
      },
    });
    // Save the new chartInstance to the chartInstances object
    chartInstances[chartName] = chartInstance;
  } else {
    // If the chartInstance already exists, update its data
    chartInstance.data.labels = epochs;
    chartInstance.data.datasets = datasets;
    chartInstance.update();
  }
};


const updateChartData = () => {
  const epochs = [...new Set(data.map(item => item.epoch))];
  const allData = {
    gasPrices: [],
    apys: [],
    commissionRates: [],
    votingPowers: [],
    stakeAmounts: [],
    rateChanges: [],
  };

  // Create datasets for each selected provider
  if (selectedProviders.value.length === 0) return

  selectedProviders.value.forEach((selectedProvider) => {
    const filteredData = data.filter((item) => item.name === selectedProvider && item.network === selectedNetwork.value);

    const epochs = filteredData.map((item) => item.epoch);
    const gasPrices = filteredData.map((item) => item.gas_price);
    const apys = filteredData.map((item) => item.apy);
    const commissionRates = filteredData.map((item) => item.commission_rate / 100);
    const votingPowers = filteredData.map((item) => item.voting_power);
    const stakeAmounts = filteredData.map((item) => item.stake / 1000000000);
    const rateChange = filteredData.map((item) => item.rate_change);

    const createDataset = (label, values) => ({
      label: selectedProvider,
      data: values,
      backgroundColor: 'rgba(75, 192, 192, 0.2)',
      borderColor: generateColorFromString(selectedProvider),
      borderWidth: 1,
      fill: false,
    });

    allData.gasPrices.push(createDataset('Gas Price', gasPrices));
    allData.apys.push(createDataset('APY', apys));
    allData.commissionRates.push(createDataset('Commission Rate', commissionRates));
    allData.votingPowers.push(createDataset('Voting Power', votingPowers));
    allData.stakeAmounts.push(createDataset('Stake Amount', stakeAmounts));
    allData.rateChanges.push(createDataset('Change Rate APY', rateChange));
  });

  // Update the charts with the new datasets
  initializeAndOrUpdateChart('epoch-gas-price-chart', epochs, allData.gasPrices);
  initializeAndOrUpdateChart('epoch-apy-chart', epochs, allData.apys);
  initializeAndOrUpdateChart('epoch-commission-rate-chart', epochs, allData.commissionRates);
  initializeAndOrUpdateChart('epoch-voting-power-chart', epochs, allData.votingPowers);
  initializeAndOrUpdateChart('epoch-stake-chart', epochs, allData.stakeAmounts);
  initializeAndOrUpdateChart('epoch-rate-change-chart', epochs, allData.rateChanges);
};

// Helper function to generate a random color
// Function to generate a color based on the string (provider name)
const golden_ratio_conjugate = 0.618033988749895;

const generateColorFromString = (str) => {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }

  // Convert hash to a number between 0 and 1
  const normalizedHash = (hash & 0xff) / 255.0;

  // Use the golden ratio to spread out the colors
  const hue = Math.floor((normalizedHash + golden_ratio_conjugate) * 360) % 360;

  return `hsl(${hue}, 80%, 60%)`;
};
watch(selectedProviders, () => {
  updateChartData();
  updateTable();
});

watch(selectedNetwork, () => {
  fetchData();
});

onMounted(() => {
  fetchData();
  updateChartData();
});

</script>

<style>
@import "vue-select/dist/vue-select.css";

.selections-container {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
  align-items: center;
}

.selection {
  display: flex;
  align-items: center;
}

.selection label {
  margin-right: 5px;
}

.charts-container {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
}

.chart {
  flex: 1 1 49%; /* Two charts per row */
  max-width: 49%; /* Two charts per row */
}

.tables-container {
  display: flex;
  flex-wrap: wrap;
}

.table-div {
  margin: auto;
  margin-top: 2%;
}

.tables-c {
  flex: 1 1 100%; /* Two charts per row */
  max-width: 100%; /* Two charts per row */
}

.style-chooser .vs__search::placeholder,
.style-chooser .vs__dropdown-toggle,
.style-chooser .vs__dropdown-menu {
  background: #333;
  border: none;
  color: #fff;
  text-transform: lowercase;
  font-variant: small-caps;
}

.style-chooser .vs__clear,
.style-chooser .vs__open-indicator {
  fill: #fff;
}

/* alt-pagination */
.alt-pagination .bh-pagination .bh-page-item {
    @apply !w-max min-w-[32px] !rounded;
}
/* next-prev-pagination */
.next-prev-pagination .bh-pagination .bh-page-item {
    @apply !w-max min-w-[100px] !rounded;
}
.next-prev-pagination .bh-pagination > div:first-child {
    @apply flex-col font-semibold;
}
.next-prev-pagination .bh-pagination .bh-pagination-number {
    @apply mx-auto gap-3;
}

/* Media query for smaller screens, one chart per row */
@media screen and (max-width: 600px) {
  .chart {
    flex: 1 1 100%; /* One chart per row */
    max-width: 100%; /* One chart per row */
  }
  .tables-c {
  flex: 1 1 100%; /* Two charts per row */
  max-width: 100%; /* Two charts per row */
}
}
</style>
