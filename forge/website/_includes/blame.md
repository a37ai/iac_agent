<canvas id="blameChart" width="800" height="360" style="margin-top: 20px"></canvas>
<canvas id="linesChart" width="800" height="360" style="margin-top: 20px"></canvas>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script src="https://cdn.jsdelivr.net/npm/moment"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-moment"></script>
<script>
document.addEventListener('DOMContentLoaded', function () {
    var blameCtx = document.getElementById('blameChart').getContext('2d');
    var linesCtx = document.getElementById('linesChart').getContext('2d');
    
    var labels = [{% for row in site.data.blame %}'{{ row.end_tag }}',{% endfor %}];
    
    var blameData = {
        labels: labels,
        datasets: [{
            label: 'forge\'s percent of new code by release',
            data: [{% for row in site.data.blame %}{ x: '{{ row.end_tag }}', y: {{ row.forge_percentage }}, lines: {{ row.forge_total }} },{% endfor %}],
            backgroundColor: 'rgba(54, 162, 235, 0.8)',
            borderColor: 'rgba(54, 162, 235, 1)',
            borderWidth: 1
        }]
    };

    var linesData = {
        labels: labels,
        datasets: [{
            label: 'forge\'s lines of new code',
            data: [{% for row in site.data.blame %}{ x: '{{ row.end_tag }}', y: {{ row.forge_total }} },{% endfor %}],
            backgroundColor: 'rgba(255, 99, 132, 0.8)',
            borderColor: 'rgba(255, 99, 132, 1)',
            borderWidth: 1
        }]
    };

    var blameChart = new Chart(blameCtx, {
        type: 'bar',
        data: blameData,
        options: {
            scales: {
                x: {
                    type: 'category',
                    title: {
                        display: true,
                        text: 'Version'
                    },
                    ticks: {
                        maxRotation: 45,
                        minRotation: 45
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Percent of new code'
                    },
                    beginAtZero: true
                }
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            var label = 'forge\'s contribution';
                            var value = context.parsed.y || 0;
                            var lines = context.raw.lines || 0;
                            return `${label}: ${Math.round(value)}% (${lines} lines)`;
                        }
                    }
                },
                title: {
                    display: true,
                    text: 'Percent of new code written by forge, by release',
                    font: {
                        size: 16
                    }
                }
            }
        }
    });

    var linesChart = new Chart(linesCtx, {
        type: 'bar',
        data: linesData,
        options: {
            scales: {
                x: {
                    type: 'category',
                    title: {
                        display: true,
                        text: 'Version'
                    },
                    ticks: {
                        maxRotation: 45,
                        minRotation: 45
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Lines of new code'
                    },
                    beginAtZero: true
                }
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            var label = 'New lines of code by forge';
                            var value = context.parsed.y || 0;
                            return `${label}: ${value}`;
                        }
                    }
                },
                title: {
                    display: true,
                    text: 'Lines of new code written by forge, by release',
                    font: {
                        size: 16
                    }
                }
            }
        }
    });
});
</script>
