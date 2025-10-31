document.addEventListener('DOMContentLoaded', () => {
    const deviceSelector = document.getElementById('device-selector');
    const metricsContainer = document.getElementById('metrics-container');
    const noDevicesMessage = document.getElementById('no-devices-message');
    let selectedDeviceId = null;
    let updateInterval = null;
    let cpuChart = null;
    let memoryChart = null;
    let diskChart = null;
    let tempChart = null;
    let voltageChart = null;

    const PREFERRED_DEVICE_KEY = 'preferredDeviceId';

    // UI Update Functions
    const updateText = (id, value) => {
        const elements = document.getElementsByClassName(id);
        for (let el of elements) {
            if (el) el.textContent = value;
        }
    };

    const updateProgressBar = (id, percentage) => {
        const el = document.getElementById(id);
        if (el) {
            el.style.width = `${percentage}%`;
            // el.textContent = `${percentage}%`; // Optional: text inside bar
        }
    };
    
    const formatUptime = (seconds) => {
        if (isNaN(seconds) || seconds < 0) {
            return "N/A";
        }
        const d = Math.floor(seconds / (3600*24));
        const h = Math.floor(seconds % (3600*24) / 3600);
        const m = Math.floor(seconds % 3600 / 60);
        
        let parts = [];
        if (d > 0) parts.push(`${d}d`);
        if (h > 0) parts.push(`${h}h`);
        if (m > 0) parts.push(`${m}m`);
        
        return parts.join(' ') || '0m';
    };

    const updateLatestMetrics = (data) => {

        updateText('hostname', data.hostname || 'N/A');
        updateText('ip_address', data.ip_address || 'N/A');

        updateText('last_seen', new Date(data.timestamp + 'Z').toLocaleString());
        updateText('uptime', formatUptime(data.uptime));

        const cpuUsage = parseFloat(data.cpu_usage).toFixed(1);
        updateText('cpu-usage', cpuUsage + ' %');
        updateProgressBar('cpu-bar', cpuUsage);

        let [cpuFreq, _] = (data.cpu_frequency || '0 0').split(' ');
        cpuFreq = parseFloat(cpuFreq).toFixed(2);
        let freqUnit = 'MHz';
        if (cpuFreq >= 1024) {
            cpuFreq = (cpuFreq / 1024).toFixed(2);
            freqUnit = 'GHz';
        }

        updateText('cpu-frequency', cpuFreq + ' ' + freqUnit || 'N/A');

        const memPerc = parseFloat(data.memory_percentage).toFixed(1);
        updateText('memory-usage', memPerc + ' %');
        updateProgressBar('memory-bar', memPerc);
        updateText('memory-used', data.memory_used);
        updateText('memory-total', data.memory_total);

        // Disk
        const diskPerc = parseFloat(data.disk_percentage).toFixed(1);
        updateText('disk-usage', diskPerc + ' %');
        updateProgressBar('disk-bar', diskPerc);
        updateText('disk-used', data.disk_used);
        updateText('disk-total', data.disk_total);

        // Temperature
        updateText('temperature', parseFloat(data.temperature).toFixed(1) + ' °C');

        // Voltages & Throttled Status
        document.getElementById('throttled').textContent = data.throttled || 'N/A';
        const throttledIndicator = document.getElementById('throttled-indicator');
        if (throttledIndicator) {
            throttledIndicator.classList.remove('status-ok', 'status-problem', 'status-unknown');
            // Use `== null` to check for both undefined and null
            if (data.throttled == null) {
                throttledIndicator.classList.add('status-unknown');
            } else if (data.throttled.trim() === '0x0') {
                throttledIndicator.classList.add('status-ok');
            } else {
                throttledIndicator.classList.add('status-problem');
            }
        }

        let voltages = null;
        if (typeof data.voltages === 'string') {
            try {
                voltages = JSON.parse(data.voltages);
            } catch (e) {
                console.error('Error parsing voltages JSON:', e);
            }
        } else if (typeof data.voltages === 'object' && data.voltages !== null) {
            voltages = data.voltages;
        }

        if (voltages) {
            document.getElementById('voltage-core').textContent = (voltages.core || 'N/A') + ' V';
            document.getElementById('voltage-sdram-c').textContent = (voltages.sdram_c || 'N/A') + ' V';
            document.getElementById('voltage-sdram-i').textContent = (voltages.sdram_i || 'N/A') + ' V';
            document.getElementById('voltage-sdram-p').textContent = (voltages.sdram_p || 'N/A') + ' V';
        } else {
            document.getElementById('voltage-core').textContent = 'N/A';
            document.getElementById('voltage-sdram-c').textContent = 'N/A';
            document.getElementById('voltage-sdram-i').textContent = 'N/A';
            document.getElementById('voltage-sdram-p').textContent = 'N/A';
        }
        
        updateNetworkStats(data.network_stats);
    };

    const updateNetworkStats = (interfaces) => {
        const container = document.getElementById('interface-list');
        if (!container) return;

        const existingInterfaces = new Set();
        container.querySelectorAll('details[data-iface-name]').forEach(el => {
            existingInterfaces.add(el.dataset.ifaceName);
        });

        const receivedInterfaces = new Set(Object.keys(interfaces || {}));

        // Remove interfaces that are no longer present
        for (const ifaceName of existingInterfaces) {
            if (!receivedInterfaces.has(ifaceName)) {
                container.querySelector(`details[data-iface-name="${ifaceName}"]`).remove();
            }
        }

        if (Object.keys(interfaces || {}).length === 0) {
            if (!container.querySelector('.no-data-message')) {
                container.innerHTML = '<p class="no-data-message">No network data available.</p>';
            }
            return;
        } else {
            const noDataMessage = container.querySelector('.no-data-message');
            if (noDataMessage) noDataMessage.remove();
        }

        let isFirstInterface = true;
        for (const ifaceName in interfaces) {
            const stats = interfaces[ifaceName];
            let details = container.querySelector(`details[data-iface-name="${ifaceName}"]`);

            if (!details) {
                // Create new element if it doesn't exist
                details = document.createElement('details');
                details.dataset.ifaceName = ifaceName;
                if (isFirstInterface) {
                    details.open = true;
                }

                const speed = stats.speed ? `${stats.speed} Mbps` : 'N/A';
                details.innerHTML = `
                    <summary class="chart-summary">
                        <span class="interface-name">${ifaceName}</span>
                        <span class="interface-speed">${speed}</span>
                    </summary>
                    <div class="interface-card">
                        <div class="network-stats">
                            <div class="network-stat">
                                <div>Sent</div>
                                <div class="network-stat-value bytes-sent">${(stats.bytes_sent || 0).toLocaleString()} Bytes</div>
                            </div>
                            <div class="network-stat">
                                <div>Received</div>
                                <div class="network-stat-value bytes-recv">${(stats.bytes_recv || 0).toLocaleString()} Bytes</div>
                            </div>
                            <div class="network-stat">
                                <div>Packets Sent</div>
                                <div class="network-stat-value packets-sent">${(stats.packets_sent || 0).toLocaleString()}</div>
                            </div>
                            <div class="network-stat">
                                <div>Packets Received</div>
                                <div class="network-stat-value packets-recv">${(stats.packets_recv || 0).toLocaleString()}</div>
                            </div>
                        </div>
                    </div>
                `;
                container.appendChild(details);
            } else {
                // Update existing element
                details.querySelector('.bytes-sent').textContent = `${(stats.bytes_sent || 0).toLocaleString()} Bytes`;
                details.querySelector('.bytes-recv').textContent = `${(stats.bytes_recv || 0).toLocaleString()} Bytes`;
                details.querySelector('.packets-sent').textContent = (stats.packets_sent || 0).toLocaleString();
                details.querySelector('.packets-recv').textContent = (stats.packets_recv || 0).toLocaleString();
                const speedEl = details.querySelector('.interface-speed');
                if (speedEl) speedEl.textContent = stats.speed ? `${stats.speed} Mbps` : '';
            }
            isFirstInterface = false;
        }
    };

    const createOrUpdateChart = (chartInstance, chartId, labels, datasets, options) => {
        if (chartInstance) {
            chartInstance.data.labels = labels;
            chartInstance.data.datasets.forEach((dataset, i) => {
                dataset.data = datasets[i].data;
            });
            chartInstance.update();
            return chartInstance;
        } else {
            const ctx = document.getElementById(chartId).getContext('2d');
            return new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: datasets
                },
                options: options
            });
        }
    };

    const updateCpuChart = (historyData) => {
        const labels = historyData.map(d => new Date(d.timestamp + 'Z').toLocaleTimeString()).reverse();
        const cpuData = historyData.map(d => d.cpu_usage).reverse();
        const datasets = [{
            label: 'CPU Usage (%)',
            data: cpuData,
            borderColor: 'rgba(75, 192, 192, 1)',
            backgroundColor: 'rgba(75, 192, 192, 0.2)',
        }];
        const options = { scales: { y: { min: 0, max: 100, title: { display: true, text: 'Usage (%)' } } } };
        cpuChart = createOrUpdateChart(cpuChart, 'cpu-chart', labels, datasets, options);
    };

    const updateMemoryChart = (historyData) => {
        const labels = historyData.map(d => new Date(d.timestamp + 'Z').toLocaleTimeString()).reverse();
        const memData = historyData.map(d => d.memory_percentage).reverse();
        const datasets = [{
            label: 'Memory Usage (%)',
            data: memData,
            borderColor: 'rgba(255, 159, 64, 1)',
            backgroundColor: 'rgba(255, 159, 64, 0.2)',
        }];
        const options = { scales: { y: { min: 0, max: 100, title: { display: true, text: 'Usage (%)' } } } };
        memoryChart = createOrUpdateChart(memoryChart, 'memory-chart', labels, datasets, options);
    };

    const updateDiskChart = (historyData) => {
        const labels = historyData.map(d => new Date(d.timestamp + 'Z').toLocaleTimeString()).reverse();
        const diskData = historyData.map(d => d.disk_percentage).reverse();
        const datasets = [{
            label: 'Disk Usage (%)',
            data: diskData,
            borderColor: 'rgba(153, 102, 255, 1)',
            backgroundColor: 'rgba(153, 102, 255, 0.2)',
        }];
        const options = { scales: { y: { min: 0, max: 100, title: { display: true, text: 'Usage (%)' } } } };
        diskChart = createOrUpdateChart(diskChart, 'disk-chart', labels, datasets, options);
    };

    const updateTempChart = (historyData) => {
        const labels = historyData.map(d => new Date(d.timestamp + 'Z').toLocaleTimeString()).reverse();
        const tempData = historyData.map(d => d.temperature).reverse();
        const datasets = [{
            label: 'Temperature (°C)',
            data: tempData,
            borderColor: 'rgba(255, 99, 132, 1)',
            backgroundColor: 'rgba(255, 99, 132, 0.2)',
        }];
        const options = { scales: { y: { title: { display: true, text: 'Temperature (°C)' } } } };
        tempChart = createOrUpdateChart(tempChart, 'temp-chart', labels, datasets, options);
    };

    const updateVoltageChart = (historyData) => {
        const labels = historyData.map(d => new Date(d.timestamp + 'Z').toLocaleTimeString()).reverse();

        const getVoltageProperty = (data, property) => {
            if (!data.voltages) return null;
            let voltageObj = data.voltages;
            if (typeof voltageObj === 'string') {
                try {
                    voltageObj = JSON.parse(voltageObj);
                } catch (e) {
                    console.error(`Error parsing voltage string: ${voltageObj}`, e);
                    return null;
                }
            }
            return voltageObj ? voltageObj[property] : null;
        };

        const voltageData = {
            core: historyData.map(d => getVoltageProperty(d, 'core')).reverse(),
            sdram_c: historyData.map(d => getVoltageProperty(d, 'sdram_c')).reverse(),
            sdram_i: historyData.map(d => getVoltageProperty(d, 'sdram_i')).reverse(),
            sdram_p: historyData.map(d => getVoltageProperty(d, 'sdram_p')).reverse(),
        };
        const datasets = [
            { label: 'Core', data: voltageData.core, borderColor: 'rgba(255, 206, 86, 1)', backgroundColor: 'rgba(255, 206, 86, 0.2)' },
            { label: 'SDRAM C', data: voltageData.sdram_c, borderColor: 'rgba(54, 162, 235, 1)', backgroundColor: 'rgba(54, 162, 235, 0.2)' },
            { label: 'SDRAM I', data: voltageData.sdram_i, borderColor: 'rgba(75, 192, 192, 1)', backgroundColor: 'rgba(75, 192, 192, 0.2)' },
            { label: 'SDRAM P', data: voltageData.sdram_p, borderColor: 'rgba(153, 102, 255, 1)', backgroundColor: 'rgba(153, 102, 255, 0.2)' }
        ];
        const options = { scales: { y: { title: { display: true, text: 'Voltage (V)' } } } };
        voltageChart = createOrUpdateChart(voltageChart, 'volt-throttle-chart', labels, datasets, options);
    };

    const updateAllCharts = (historyData) => {
        updateCpuChart(historyData);
        updateMemoryChart(historyData);
        updateDiskChart(historyData);
        updateTempChart(historyData);
        updateVoltageChart(historyData);
    };

    const fetchData = async () => {
        if (selectedDeviceId === null || selectedDeviceId === undefined) {
            return;
        }
        try {
            const [latestRes, historyRes] = await Promise.all([
                fetch(`/api/latest/${selectedDeviceId}`),
                fetch(`/api/history/${selectedDeviceId}`)
            ]);
            if (!latestRes.ok || !historyRes.ok) {
                console.error('Failed to fetch data for device', selectedDeviceId);
                return;
            }
            const latestData = await latestRes.json();
            const historyData = await historyRes.json();
            
            updateLatestMetrics(latestData);
            updateAllCharts(historyData);

        } catch (error) {
            console.error('Error fetching data:', error);
        }
    };

    const loadDevices = async () => {
        try {
            const response = await fetch('/api/devices');
            const devices = await response.json();

            if (devices.length === 0) {
                metricsContainer.classList.add('hidden');
                noDevicesMessage.classList.remove('hidden');
                return;
            }

            metricsContainer.classList.remove('hidden');
            noDevicesMessage.classList.add('hidden');

            deviceSelector.innerHTML = '';
            devices.forEach(device => {
                const option = document.createElement('option');
                option.value = device.id;
                option.textContent = `${device.device_name || device.hostname} (ID: ${device.id} / Addr: ${device.ip_address})`;
                deviceSelector.appendChild(option);
            });

            const preferredId = localStorage.getItem(PREFERRED_DEVICE_KEY);
            if (preferredId && devices.some(d => d.id == preferredId)) {
                deviceSelector.value = preferredId;
            }
            
            selectedDeviceId = deviceSelector.value;
            startUpdating();

        } catch (error) {
            console.error('Failed to load devices:', error);
            metricsContainer.classList.add('hidden');
            noDevicesMessage.classList.remove('hidden');
            noDevicesMessage.innerHTML = '<h2>Error loading devices.</h2><p>Could not connect to the server.</p>';
        }
    };

    const startUpdating = () => {
        if (updateInterval) {
            clearInterval(updateInterval);
        }
        fetchData(); // Fetch immediately
        updateInterval = setInterval(fetchData, 5000); // Then every 5 seconds
    };

    deviceSelector.addEventListener('change', () => {
        selectedDeviceId = deviceSelector.value;
        localStorage.setItem(PREFERRED_DEVICE_KEY, selectedDeviceId);
        startUpdating();
    });

    document.getElementById('toggle-details').addEventListener('click', (e) => {
        e.preventDefault();
        const detailsContent = document.getElementById('details-content');
        const toggleButton = e.target;

        if (detailsContent.style.display === 'none') {
            detailsContent.style.display = 'block';
            toggleButton.textContent = 'Hide Voltage Details';
        } else {
            detailsContent.style.display = 'none';
            toggleButton.textContent = 'Show Voltage Details';
        }
    });

    // Initial load
    loadDevices();

    // --- Collapsible Chart State Persistence ---
    const loadChartStates = () => {
        document.querySelectorAll('.chart-details').forEach(details => {
            const canvas = details.querySelector('canvas');
            if (canvas && canvas.id) {
                const savedState = localStorage.getItem(`chart-state-${canvas.id}`);
                if (savedState !== null) {
                    details.open = (savedState === 'true');
                }
            }
        });
    };

    // Add event listeners to save state on change.
    // This is more efficient as it only saves the state for the toggled element.
    metricsContainer.addEventListener('click', (event) => {
        const summary = event.target.closest('summary');
        if (summary && summary.parentElement.classList.contains('chart-details')) {
            const details = summary.parentElement;
            const canvas = details.querySelector('canvas');
            // State is toggled after the click, so use a timeout to get the new state
            setTimeout(() => {
                if (canvas && canvas.id) {
                    localStorage.setItem(`chart-state-${canvas.id}`, details.open);
                }
            }, 0);
        }
    });

    // Load initial states when the page is ready
    loadChartStates();
});
