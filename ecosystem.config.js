module.exports = {
  apps : [{
    name: 'LeakixResultPublisher',
    script: 'publish_results.py',
    interpreter: '/usr/bin/python3', // Specify the path to the Python interpreter
    instances: 1,
    autorestart: false,
    watch: false,
    max_memory_restart: '1G',
    cron_restart: '*/1 * * * *', // This cron pattern means every minute
    exec_mode: 'fork'
  }]
};
