// pm2 ecosystem config for dod-ocr backend.
// Frontend is a static build served by nginx — not managed by pm2.
// .env is auto-loaded by app/main.py via python-dotenv.
module.exports = {
  apps: [
    {
      name: "dod-ocr-backend",
      cwd: "/opt/dod-ocr/backend",
      script: "/home/ubuntu/.local/bin/uv",
      args: "run uvicorn app.main:app --host 127.0.0.1 --port 8000",
      interpreter: "none",
      env: {
        ROOT_PATH: "/app/pdfextractor/api",
      },
      autorestart: true,
      max_restarts: 10,
      restart_delay: 3000,
      kill_timeout: 10000,
      out_file: "/var/log/dod-ocr/backend.out.log",
      error_file: "/var/log/dod-ocr/backend.err.log",
      merge_logs: true,
      time: true,
    },
  ],
};
