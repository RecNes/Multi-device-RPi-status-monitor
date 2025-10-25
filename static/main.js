const tempCtx = document.getElementById('temp-chart').getContext('2d');
const tempChart = new Chart(tempCtx, {
    type: 'line',
    data: {
        labels: [],
        datasets: [{
            label: 'Temperature (°C)',
            data: [],
            borderColor: '#f39c12',
            backgroundColor: 'rgba(243, 156, 18, 0.1)',
            borderWidth: 2,
            fill: true,
            tension: 0.4
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
            y: {
                beginAtZero: true
            }
        },
        plugins: {
            legend: {
                display: false
            }
        }
    }
});

// Combined Voltage and Throttle chart
const voltThrottleCtx = document.getElementById('volt-throttle-chart').getContext('2d');
const voltageKeys = ['core', 'sdram_c', 'sdram_i', 'sdram_p'];
const voltageColors = {
    core: '#27ae60',
    sdram_c: '#2980b9',
    sdram_i: '#8e44ad',
    sdram_p: '#f39c12'
};
const voltageBGColors = {
    core: 'rgba(39,174,96,0.08)',
    sdram_c: 'rgba(41,128,185,0.08)',
    sdram_i: 'rgba(142,68,173,0.08)',
    sdram_p: 'rgba(243,156,18,0.08)'
};

const voltDatasets = voltageKeys.map(k => ({
    label: k.replace('_', ' ').toUpperCase(),
    data: [],
    borderColor: voltageColors[k] || '#999',
    backgroundColor: voltageBGColors[k] || 'rgba(0,0,0,0.04)',
    fill: true,
    tension: 0.3,
    yAxisID: 'y'
}));

const throttleDataset = {
    label: 'Throttle flags (decimal)',
    data: [],
    borderColor: '#c0392b',
    backgroundColor: 'rgba(192,57,43,0.08)',
    fill: true,
    tension: 0.4,
    yAxisID: 'y1'
};

const voltThrottleChart = new Chart(voltThrottleCtx, {
    type: 'line',
    data: { 
        labels: [], 
        datasets: [...voltDatasets, throttleDataset] 
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
            y: {
                type: 'linear',
                display: true,
                position: 'left',
                beginAtZero: false
            },
            y1: {
                type: 'linear',
                display: true,
                position: 'right',
                grid: {
                    drawOnChartArea: false
                },
                beginAtZero: true
            }
        },
        plugins: { 
            legend: { 
                display: true 
            } 
        }
    }
});

function createUsageChart(elementId, label, color) {
    const ctx = document.getElementById(elementId).getContext('2d');
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: label,
                data: [],
                borderColor: color,
                backgroundColor: color.replace('1)', '0.1)'),
                borderWidth: 2,
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100
                }
            },
            plugins: {
                legend: {
                    display: false
                }
            }
        }
    });
}

const cpuChart = createUsageChart('cpu-chart', 'CPU Usage (%)', 'rgba(52, 152, 219, 1)');
const memoryChart = createUsageChart('memory-chart', 'Memory Usage (%)', 'rgba(46, 204, 113, 1)');
const diskChart = createUsageChart('disk-chart', 'Disk Usage (%)', 'rgba(231, 76, 60, 1)');


function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function updateProgressBar(element, percentage) {
    element.classList.remove('low', 'medium', 'high');
    
    if (percentage < 50) {
        element.classList.add('low');
    } else if (percentage < 80) {
        element.classList.add('medium');
    } else {
        element.classList.add('high');
    }
    
    element.style.width = percentage + '%';
}

function fetchSystemInfo() {
    fetch('/api/system-info')
        .then(response => response.json())
        .then(data => {
            document.getElementById('cpu-usage').textContent = data.cpu.usage + '%';
            document.getElementById('cpu-percentage').textContent = data.cpu.usage + '%';
            document.getElementById('cpu-frequency').textContent = data.cpu.frequency;
            updateProgressBar(document.getElementById('cpu-progress'), data.cpu.usage);

            document.getElementById('memory-usage').textContent = 
                data.memory.used + ' GB / ' + data.memory.total + ' GB';
            document.getElementById('memory-percentage').textContent = data.memory.percentage + '%';
            updateProgressBar(document.getElementById('memory-progress'), data.memory.percentage);

            document.getElementById('disk-usage').textContent = 
                data.disk.used + ' GB / ' + data.disk.total + ' GB';
            document.getElementById('disk-percentage').textContent = data.disk.percentage + '%';
            updateProgressBar(document.getElementById('disk-progress'), data.disk.percentage);

            document.getElementById('temperature').textContent = data.temperature + '°C';

            // Update throttled and voltages
            const throttledEl = document.getElementById('throttled');
            const voltageEl = document.getElementById('voltage-core');
            const sdramCEl = document.getElementById('voltage-sdram-c');
            const sdramIEl = document.getElementById('voltage-sdram-i');
            const sdramPEl = document.getElementById('voltage-sdram-p');
            throttledEl.textContent = data.throttled || 'N/A';
            const vcore = data.voltages && data.voltages.core ? data.voltages.core : null;
            const vsdramC = data.voltages && data.voltages.sdram_c ? data.voltages.sdram_c : null;
            const vsdramI = data.voltages && data.voltages.sdram_i ? data.voltages.sdram_i : null;
            const vsdramP = data.voltages && data.voltages.sdram_p ? data.voltages.sdram_p : null;
            voltageEl.textContent = vcore !== null ? vcore : 'N/A';
            sdramCEl.textContent = vsdramC !== null ? vsdramC : 'N/A';
            sdramIEl.textContent = vsdramI !== null ? vsdramI : 'N/A';
            sdramPEl.textContent = vsdramP !== null ? vsdramP : 'N/A';
            
            updateVoltThrottleChart(data.voltages || {}, data.throttled ? parseInt(data.throttled, 16) : null);

            const interfaceList = document.getElementById('interface-list');
            interfaceList.innerHTML = '';
            
            Object.entries(data.network.interfaces).forEach(([iface, stats]) => {
                if (stats.is_up) {
                    const interfaceCard = document.createElement('div');
                    interfaceCard.className = 'interface-card';
                    
                    const title = document.createElement('h3');
                    title.textContent = iface;
                    interfaceCard.appendChild(title);
                    
                    if (stats.speed) {
                        const speed = document.createElement('div');
                        speed.className = 'interface-speed';
                        speed.textContent = `${stats.speed} Mbps`;
                        interfaceCard.appendChild(speed);
                    }
                    
                    const statsDiv = document.createElement('div');
                    statsDiv.className = 'network-stats';
                    statsDiv.innerHTML = `
                        <div class="network-stat">
                            <div>Sent</div>
                            <div class="network-stat-value">${formatBytes(stats.bytes_sent)}</div>
                        </div>
                        <div class="network-stat">
                            <div>Received</div>
                            <div class="network-stat-value">${formatBytes(stats.bytes_recv)}</div>
                        </div>
                        <div class="network-stat">
                            <div>Packets Sent</div>
                            <div class="network-stat-value">${stats.packets_sent.toLocaleString()}</div>
                        </div>
                        <div class="network-stat">
                            <div>Packets Received</div>
                            <div class="network-stat-value">${stats.packets_recv.toLocaleString()}</div>
                        </div>
                    `;
                    interfaceCard.appendChild(statsDiv);
                    interfaceList.appendChild(interfaceCard);
                }
            });

            document.getElementById('uptime').textContent = data.uptime;

            updateTempChart(data.temperature);
            updateUsageChart(cpuChart, data.cpu.usage);
            updateUsageChart(memoryChart, data.memory.percentage);
            updateUsageChart(diskChart, data.disk.percentage);
        })
        .catch(error => {
            console.error('Error fetching system info:', error);
        });
}

function updateTempChart(temperature) {
    const now = new Date();
    const timeString = now.getHours() + ':' + (now.getMinutes() < 10 ? '0' : '') + now.getMinutes();

    tempChart.data.labels.push(timeString);
    tempChart.data.datasets[0].data.push(temperature);

    if (tempChart.data.labels.length > 20) {
        tempChart.data.labels.shift();
        tempChart.data.datasets[0].data.shift();
    }

    tempChart.update();
}

function updateUsageChart(chart, value) {
    const now = new Date();
    const timeString = now.getHours() + ':' + (now.getMinutes() < 10 ? '0' : '') + now.getMinutes();

    chart.data.labels.push(timeString);
    chart.data.datasets[0].data.push(value);

    if (chart.data.labels.length > 20) {
        chart.data.labels.shift();
        chart.data.datasets[0].data.shift();
    }

    chart.update();
}

function updateVoltThrottleChart(volts, throttleValue) {
    const now = new Date();
    const timeString = now.getHours() + ':' + (now.getMinutes() < 10 ? '0' : '') + now.getMinutes();
    
    voltThrottleChart.data.labels.push(timeString);

    voltageKeys.forEach((k, idx) => {
        const val = (volts && typeof volts[k] !== 'undefined' && volts[k] !== null) ? volts[k] : null;
        voltThrottleChart.data.datasets[idx].data.push(val);
    });
    
    voltThrottleChart.data.datasets[voltageKeys.length].data.push(throttleValue);

    if (voltThrottleChart.data.labels.length > 40) {
        voltThrottleChart.data.labels.shift();
        voltThrottleChart.data.datasets.forEach(ds => ds.data.shift());
    }
    voltThrottleChart.update();
}

function seedHistory() {
    fetch('/api/history')
        .then(r => r.json())
        .then(history => {
            history.reverse();
            history.forEach(point => {
                const t = new Date(point.timestamp);
                const label = t.getHours() + ':' + (t.getMinutes() < 10 ? '0' : '') + t.getMinutes();
                
                tempChart.data.labels.push(label);
                tempChart.data.datasets[0].data.push(point.temperature);
                
                cpuChart.data.labels.push(label);
                cpuChart.data.datasets[0].data.push(point.cpu_usage);
                
                memoryChart.data.labels.push(label);
                memoryChart.data.datasets[0].data.push(point.memory_percentage);
                
                diskChart.data.labels.push(label);
                diskChart.data.datasets[0].data.push(point.disk_percentage);

                voltThrottleChart.data.labels.push(label);
                voltageKeys.forEach((k, idx) => {
                    const v = (point.voltages && typeof point.voltages[k] !== 'undefined') ? point.voltages[k] : null;
                    voltThrottleChart.data.datasets[idx].data.push(v);
                });

                const throttleVal = point.throttled ? parseInt(point.throttled, 16) : null;
                voltThrottleChart.data.datasets[voltageKeys.length].data.push(throttleVal);
            });
            tempChart.update();
            voltThrottleChart.update();
            cpuChart.update();
            memoryChart.update();
            diskChart.update();
        })
        .catch(err => console.warn('Could not load history:', err));
}

// Initial data load
seedHistory();
fetchSystemInfo();

// Update every 5 seconds (5000 milliseconds)
setInterval(fetchSystemInfo, 5000);

// Add error handling for failed API calls
window.addEventListener('unhandledrejection', function(event) {
    console.error('API call failed:', event.reason);
});

document.addEventListener('DOMContentLoaded', function() {
    const toggleButton = document.getElementById('toggle-details');
    const detailsContent = document.getElementById('details-content');

    toggleButton.addEventListener('click', function(event) {
        event.preventDefault();
        if (detailsContent.style.display === 'none') {
            detailsContent.style.display = 'block';
            toggleButton.textContent = 'Hide Voltage Details';
        } else {
            detailsContent.style.display = 'none';
            toggleButton.textContent = 'Show Voltage Details';
        }
    });
});
