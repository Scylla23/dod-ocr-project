# Deployment

Single-VM Oracle Cloud deploy. Nginx serves static frontend, reverse-proxies backend on port 8000. Systemd manages uvicorn. GitHub Actions SSHes into VM on push to `main` and runs `deploy/deploy.sh`.

## Files

- `dod-ocr-backend.service` — installed at `/etc/systemd/system/dod-ocr-backend.service`
- `nginx.conf` — installed at `/etc/nginx/sites-available/dod-ocr`, symlinked into `sites-enabled`
- `sudoers.dod-ocr` — installed at `/etc/sudoers.d/dod-ocr` (mode 0440), grants `ubuntu` passwordless restart of backend and nginx reload
- `deploy.sh` — idempotent deploy run by CI on the server
- `../.github/workflows/deploy.yml` — pushes to `main` trigger SSH deploy

## Required GitHub Actions secrets

- `OCI_HOST` — public IP or domain
- `OCI_USER` — `ubuntu`
- `OCI_SSH_KEY` — full private key contents (`-----BEGIN OPENSSH PRIVATE KEY-----` ... `-----END OPENSSH PRIVATE KEY-----`)
- `OCI_PORT` — `22`

## Backend `.env`

Lives at `/opt/dod-ocr/backend/.env` on server (gitignored). Provision once by hand. Restart backend after changes:

```
sudo systemctl restart dod-ocr-backend
```

## Adding HTTPS later

Point a domain at the public IP, then on the server:

```
sudo certbot --nginx -d yourdomain.com
```

Certbot rewrites `nginx.conf` in place — re-running `deploy.sh` will not undo it.
