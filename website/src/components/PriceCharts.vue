<template>
  <div>
    <div class="selections-container">
      <div class="selection">
        <label for="provider">Validator</label>
        <select v-model="selectedProvider" @change="updateChartData">
          <option v-for="provider in providers" :key="provider" :value="provider">
            {{ provider }}
          </option>
        </select>
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
import "@bhplugin/vue3-datatable/dist/style.css";

// Register the necessary plugins
Chart.register(...registerables);

const chartRef = ref(null);
const selectedProvider = ref('Blockdaemon');
const selectedNetwork = ref('mainnet');
const gasPriceChart = ref(null);
const apyChart = ref(null);
const commissionRateChart = ref(null);
const votingPowerChart = ref(null);
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
      { field: "epoch", title: "Epoch", isUnique: true},
      { field: "gasPrice", title: "Gas Price" },
      { field: "apy", title: "APY" },
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
  const filteredData = data.filter((item) => item.name === selectedProvider.value && item.network === selectedNetwork.value);

  // Extract the required data
  const tableData = filteredData.map((item) => ({
    epoch: item.epoch,
    gasPrice: item.gas_price,
    apy: (item.apy * 100).toFixed(4) + '%',
    commissionRate: item.commission_rate / 100 + '%',
    votingPower: item.voting_power,
    stakeAmount: (item.stake / 1000000000).toLocaleString('en-US', {minimumFractionDigits: 2,maximumFractionDigits: 2})
  }));

  // Assuming you have a reactive reference to store the table data
  tableDataRef.value = tableData;
};

const downloadCSV = async () => {
  try {
    const url = `${baseUrl}/csv?name=${selectedProvider.value}&network=${selectedNetwork.value}`;
    const response = await axios.get(url, { responseType: 'blob' });
    const blob = new Blob([response.data], { type: 'text/csv;charset=utf-8' });
    const link = document.createElement('a');
    link.href = window.URL.createObjectURL(blob);
    link.download = `${selectedProvider.value}.csv`;
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
const initializeChart = (chartName, labels, values, label) => {
  const canvas = document.getElementById(chartName);
  if (canvas) {
    const ctx = canvas.getContext('2d');
    return new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{
          label: label,
          data: values,
          backgroundColor: 'rgba(75, 192, 192, 0.2)',
          borderColor: 'rgba(75, 192, 192, 1)',
          borderWidth: 1,
          fill: false,
        }],
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

const initializeAndOrUpdateChart = (chartName, labels, values, label) => {
  if (!chartInstances[chartName]) {
    chartInstances[chartName] = initializeChart(chartName, labels, values, label);
  } else {
    const chartInstance = chartInstances[chartName];
    chartInstance.data.labels = labels;
    chartInstance.data.datasets[0].data = values;
    chartInstance.update();
  }
};



const updateChartData = () => {
  // Filter data based on selected provider and network
  const filteredData = data.filter(
    (item) => item.name === selectedProvider.value && item.network === selectedNetwork.value
  );

  const epochs = filteredData.map((item) => item.epoch);
  const gasPrices = filteredData.map((item) => item.gas_price);
  const apys = filteredData.map((item) => item.apy);
  const commissionRates = filteredData.map((item) => item.commission_rate / 100);
  const votingPowers = filteredData.map((item) => item.voting_power);
  const stakeAmount = filteredData.map((item) => item.stake / 1000000000 );

  initializeAndOrUpdateChart('epoch-gas-price-chart', epochs, gasPrices, 'Gas Price');
  initializeAndOrUpdateChart('epoch-apy-chart', epochs, apys, 'APY');
  initializeAndOrUpdateChart('epoch-commission-rate-chart', epochs, commissionRates, 'Commission Rate');
  initializeAndOrUpdateChart('epoch-voting-power-chart', epochs, votingPowers, 'Voting Power');
  initializeAndOrUpdateChart('epoch-stake-chart', epochs, stakeAmount, 'Stake Amount');
};


watch(selectedProvider, () => {
  updateChartData();
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
