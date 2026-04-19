# Auto Deploy To DigitalOcean

This repository uses GitHub Actions to deploy automatically to a DigitalOcean Droplet on every push to `main`.

Workflow file:
- `.github/workflows/deploy-digitalocean.yml`

## How It Works

1. GitHub Action connects to droplet over SSH.
2. It pulls latest `main` into `/opt/assignment-notifier`.
3. It installs dependencies in `.venv`.
4. It restarts `assignment-notifier` service with `systemctl`.

## Repository Secrets

Add these in `Settings` -> `Secrets and variables` -> `Actions`:

- `DROPLET_HOST`: droplet public IP (example `203.0.113.10`)
- `DROPLET_USER`: SSH user (recommended `deploy`)
- `DROPLET_SSH_KEY`: private SSH key for `DROPLET_USER`

## Droplet Requirements

- App path exists: `/opt/assignment-notifier`
- Virtual environment exists: `/opt/assignment-notifier/.venv`
- Service exists: `assignment-notifier`
- `deploy` can run service commands without password

Use this sudoers rule:

```bash
echo 'deploy ALL=(ALL) NOPASSWD:/usr/bin/systemctl restart assignment-notifier,/usr/bin/systemctl is-active assignment-notifier,/usr/bin/systemctl is-active --quiet assignment-notifier' | sudo tee /etc/sudoers.d/deploy-assignment-notifier
sudo chmod 440 /etc/sudoers.d/deploy-assignment-notifier
sudo visudo -cf /etc/sudoers.d/deploy-assignment-notifier
```

## Install Public Key On Droplet

Add the public key that matches `DROPLET_SSH_KEY`:

```bash
install -d -m 700 -o deploy -g deploy /home/deploy/.ssh
echo "ssh-ed25519 AAAA... your-key-comment" | sudo tee -a /home/deploy/.ssh/authorized_keys
sudo chown deploy:deploy /home/deploy/.ssh/authorized_keys
sudo chmod 600 /home/deploy/.ssh/authorized_keys
```

## Run And Verify

1. Push to `main` or run workflow manually from Actions tab.
2. Verify service:

```bash
sudo systemctl is-active assignment-notifier
journalctl -u assignment-notifier -n 100 --no-pager
```

## Troubleshooting

- `missing server host`
  - `DROPLET_HOST` secret is missing or empty.

- `ssh.ParsePrivateKey: ssh: no key found`
  - `DROPLET_SSH_KEY` is not a valid private key block.

- `unable to authenticate, attempted methods [none publickey]`
  - Public key is not installed for `DROPLET_USER` on droplet.

- `sudo: a password is required`
  - Sudoers rule is missing or does not match exact command arguments.

## Security Notes

- Never commit secrets or private keys.
- Use a dedicated deploy key (do not reuse personal keys).
- Rotate deploy key immediately if exposed.
- Restrict sudoers scope to only required `systemctl` commands.
