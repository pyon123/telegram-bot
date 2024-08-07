module.exports = {
  apps: [
    {
      name: 'main',
      script: 'main.py',
      interpreter: '/usr/bin/python3',
      instances: 1,
      autorestart: false,
      watch: false,
      max_memory_restart: '1G',
      exec_mode: 'fork',
      cwd: '/root/telegram-bot'
    },
    {
      name: 'publisher',
      script: 'publish.py',
      interpreter: '/usr/bin/python3',
      instances: 1,
      autorestart: false,
      watch: false,
      max_memory_restart: '500M',
      cron_restart: '0 * * * *', // every 1 hour
      exec_mode: 'fork',
      cwd: '/root/telegram-bot'
    },
    {
      name: 'search',
      script: 'search.py',
      interpreter: '/usr/bin/python3',
      instances: 1,
      autorestart: false,
      watch: false,
      max_memory_restart: '1G',
      cron_restart: '0 */12 * * *', // every 12 hours
      exec_mode: 'fork',
      cwd: '/root/telegram-bot'
    },
  ]
};
