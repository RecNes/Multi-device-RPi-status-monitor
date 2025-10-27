document.addEventListener('DOMContentLoaded', () => {
    const deviceSelector = document.getElementById('device-selector');
    const metricsContainer = document.getElementById('metrics-container');
    const noDevicesMessage = document.getElementById('no-devices-message');
    let selectedDeviceId = null;
    let updateInterval = null;
    let historyChart = null;

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

        let [cpuFreq, _] = data.cpu_frequency.split(' ');
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
    };

    const updateHistoryChart = (historyData) => {
        const labels = historyData.map(d => new Date(d.timestamp + 'Z').toLocaleTimeString()).reverse();
        const cpuData = historyData.map(d => d.cpu_usage).reverse();
        const memData = historyData.map(d => d.memory_percentage).reverse();
        const tempData = historyData.map(d => d.temperature).reverse();

        if (historyChart) {
            historyChart.data.labels = labels;
            historyChart.data.datasets[0].data = cpuData;
            historyChart.data.datasets[1].data = memData;
            historyChart.data.datasets[2].data = tempData;
            historyChart.update();
        } else {
            const ctx = document.getElementById('history-chart').getContext('2d');
            historyChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'CPU Usage (%)',
                            data: cpuData,
                            borderColor: 'rgba(75, 192, 192, 1)',
                            backgroundColor: 'rgba(75, 192, 192, 0.2)',
                            yAxisID: 'y',
                        },
                        {
                            label: 'Memory Usage (%)',
                            data: memData,
                            borderColor: 'rgba(255, 159, 64, 1)',
                            backgroundColor: 'rgba(255, 159, 64, 0.2)',
                            yAxisID: 'y',
                        },
                        {
                            label: 'Temperature (°C)',
                            data: tempData,
                            borderColor: 'rgba(255, 99, 132, 1)',
                            backgroundColor: 'rgba(255, 99, 132, 0.2)',
                            yAxisID: 'y1',
                        }
                    ]
                },
                options: {
                    scales: {
                        y: {
                            type: 'linear',
                            display: true,
                            position: 'left',
                            min: 0,
                            max: 100,
                            title: {
                                display: true,
                                text: 'Usage (%)'
                            }
                        },
                        y1: {
                            type: 'linear',
                            display: true,
                            position: 'right',
                            title: {
                                display: true,
                                text: 'Temperature (°C)'
                            },
                            grid: {
                                drawOnChartArea: false, 
                            },
                        }
                    }
                }
            });
        }
    };

    const fetchData = async () => {
        if (!selectedDeviceId) return;
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
            updateHistoryChart(historyData);

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

    // Initial load
    loadDevices();
});
