# Deployment

Single-VM Oracle Cloud deploy. Nginx serves the static frontend and reverse-proxies the backend on port 8000. **pm2** manages the uvicorn process. GitHub Actions SSHes into the VM on push to `main` and runs `deploy/deploy.sh`.

## Files

- `ecosystem.config.cjs` — pm2 app definition for the backend
- `nginx.conf` — installed at `/etc/nginx/sites-available/dod-ocr`, symlinked into `sites-enabled`
- `sudoers.dod-ocr` — installed at `/etc/sudoers.d/dod-ocr` (mode 0440); grants `ubuntu` passwordless `nginx reload` only
- `deploy.sh` — idempotent deploy run by CI on the server
- `../.github/workflows/deploy.yml` — pushes to `main` trigger the SSH deploy

## Required GitHub Actions secrets

- `OCI_HOST` — public IP or domain
- `OCI_USER` — `ubuntu`
- `OCI_SSH_KEY` — full private key contents (`-----BEGIN OPENSSH PRIVATE KEY-----` ... `-----END OPENSSH PRIVATE KEY-----`)
- `OCI_PORT` — `22`

## Backend `.env`

Lives at `/opt/dod-ocr/backend/.env` on the server (gitignored). Provisioned manually. Auto-loaded by `app/main.py` via `python-dotenv`. After editing `.env`, reload backend:

```
pm2 reload dod-ocr-backend --update-env
```

## pm2 startup (one-time, run as ubuntu on server)

```
sudo npm install -g pm2
sudo mkdir -p /var/log/dod-ocr && sudo chown ubuntu:ubuntu /var/log/dod-ocr
pm2 start /opt/dod-ocr/deploy/ecosystem.config.cjs
pm2 save
sudo env PATH=$PATH:/usr/bin pm2 startup systemd -u ubuntu --hp /home/ubuntu
```

## Adding HTTPS later

Point a domain at the public IP, then on the server:

```
sudo certbot --nginx -d yourdomain.com
```

Certbot rewrites `nginx.conf` in place — re-running `deploy.sh` will not undo it.
