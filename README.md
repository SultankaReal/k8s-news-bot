# ☸️ k8s-news-bot

Automated Kubernetes & DevOps digest bot. Runs a daily email digest and a weekly deep-research report — entirely self-hosted, no cloud AI APIs required.

**What it does:**
- **Daily digest** — fetches RSS from Habr, Yandex Cloud, Kubernetes.io, CNCF, InfoQ, AWS/GKE blogs, Prometheus, Grafana + runs an LLM-powered English research query via GPT Researcher. Delivers a combined digest to your inbox every morning.
- **Weekly report** — runs 5 focused research queries (Kubernetes releases, CNCF, managed K8s, observability, Russian-language sources) and sends a comprehensive analytical report every Monday.

All LLM inference and embeddings run locally via **Ollama** (`mistral:7b`). No OpenAI key needed.

---

## Architecture

```mermaid
flowchart TD
    subgraph VM["Linux VM (Docker Compose)"]
        direction TB

        subgraph Ollama["ollama — Local LLM"]
            O1["mistral:7b\nLLM inference"]
            O2["nomic-embed-text\nEmbeddings"]
        end

        subgraph GPTR["gptr — GPT Researcher"]
            G1["Research engine\n:8000/report/"]
            G2["DuckDuckGo search\n(web retriever)"]
        end

        subgraph Bot["news-bot — Scheduler"]
            B1["APScheduler\nCron jobs"]
            B2["RSS Fetcher\nHabr · Yandex Cloud\n+ 10 EN feeds"]
            B3["gptr client\nHTTP POST /report/"]
            B4["Email delivery\nSMTP Yandex"]
        end

        Ollama -->|"OpenAI-compatible API\nhttp://ollama:11434/v1"| GPTR
        GPTR -->|"Markdown report"| Bot
        B2 -->|"Articles"| B1
        B3 -->|"Research query"| G1
        B1 -->|"Daily 06:00 UTC\nWeekly Mon 07:00 UTC"| B4
    end

    Internet["🌐 Internet\nRSS feeds · DuckDuckGo"] -->|"RSS/HTTP"| B2
    Internet -->|"Web search"| G2
    B4 -->|"SMTP :465 SSL"| Email["📧 Yandex Mail\nInbox"]
```

---

## Prerequisites

| Requirement | Details |
|---|---|
| **Linux VM** | Ubuntu 22.04+, **8 vCPU / 8 GB RAM minimum** (mistral:7b needs ~5 GB RAM) |
| **Docker Engine 24+** | With the **Compose plugin** — use `docker compose` (v2), not the old standalone `docker-compose` (v1) |
| **make** | Standard build tool — `sudo apt install make` |
| **Yandex Mail account** | For SMTP delivery (app password, not regular password) |
| **Disk** | ~10 GB free (Ollama model storage + Docker images) |

> **Note:** mistral:7b runs on CPU, but first inference after container start takes 2–4 minutes. 8 cores keep the daily digest latency tolerable (typically 5–10 min end-to-end); it will still run on 4 cores, just noticeably slower.

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/SultankaReal/k8s-news-bot.git
cd k8s-news-bot
```

### 2. Create your `.env` file

```bash
cp .env.example .env
nano .env
```

Fill in the required values:

```env
# Your Yandex Mail address
EMAIL_FROM=your@yandex.ru

# App password (NOT your regular password!)
# Create at: https://id.yandex.ru/security/app-passwords
EMAIL_PASSWORD=your_app_password_here

# Recipient — defaults to EMAIL_FROM if not set
EMAIL_TO=your@yandex.ru
```

### 3. Install Docker + Docker Compose (if not already installed)

```bash
# Ubuntu / Debian — installs Docker Engine + Compose plugin + BuildKit in one go
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# Install make
sudo apt install -y make

# Verify both are working
docker version          # should show Engine 24+
docker compose version  # should show Docker Compose v2.x
```

> **Important:** this project uses `docker compose` (v2, the plugin). The old standalone `docker-compose` (v1) is not supported and will fail.

### 4. Start the stack

```bash
make up
# or: docker compose up -d
```

This starts three services in order:
1. **ollama** — downloads and serves `mistral:7b` (~4 GB, one-time download)
2. **gptr** — GPT Researcher web service (waits for Ollama healthcheck)
3. **news-bot** — scheduler with cron jobs (waits for gptr healthcheck)

> First startup takes **10–15 minutes** while Ollama downloads the model. Check progress with `make logs`.

### 5. Pull the Ollama model (first run)

The gptr service will automatically try to pull the model via Ollama on first use. You can also pre-pull it manually:

```bash
docker compose exec ollama ollama pull mistral:7b
docker compose exec ollama ollama pull nomic-embed-text
```

### 6. Verify the stack is running

```bash
make status
# or: docker compose ps
```

All three services should show `healthy` status.

### 7. Test a digest immediately

```bash
# Run daily digest right now (bypasses the cron schedule)
make test-daily

# Run weekly report right now
make test-weekly
```

Check your inbox within 5–10 minutes.

---

## Configuration

All settings are via environment variables in `.env`:

| Variable | Default | Description |
|---|---|---|
| `EMAIL_FROM` | — | Sender Yandex Mail address |
| `EMAIL_PASSWORD` | — | Yandex Mail app password |
| `EMAIL_TO` | `EMAIL_FROM` | Recipient address |
| `DAILY_DIGEST_CRON` | `0 6 * * *` | Daily digest schedule (UTC cron) |
| `WEEKLY_REPORT_CRON` | `0 7 * * 1` | Weekly report schedule (UTC cron) |
| `GPTR_TIMEOUT` | `900` | Max seconds to wait for GPT Researcher (LLM on CPU is slow) |
| `FAST_LLM` | `ollama:mistral:7b` | LLM for GPT Researcher fast tasks |
| `SMART_LLM` | `ollama:mistral:7b` | LLM for GPT Researcher smart tasks |
| `RETRIEVER` | `duckduckgo` | Web retriever for GPT Researcher |
| `GPTR_OUTPUTS_MAX_AGE_DAYS` | `7` | Days to keep GPT Researcher output files |
| `LOG_LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`) |
| `RUN_DAILY_NOW` | `0` | Set to `1` to run daily digest on container start |
| `RUN_WEEKLY_NOW` | `0` | Set to `1` to run weekly report on container start |

---

## RSS Sources

The bot fetches from 18 RSS feeds across two tracks:

**Russian sources** (included in every daily digest):
- Habr: kubernetes, devops, monitoring, cloud_computing, sys_admin, linux hubs
- Yandex Cloud blog

**English sources** (fetched for context, processed by GPT Researcher):
- kubernetes.io, cncf.io, thenewstack.io, infoq.com
- AWS Containers blog, Google Cloud / GKE blog
- devops.com, prometheus.io, grafana.com

---

## Deploy to Yandex Cloud VM

The `infra/` directory contains helpers for Yandex Cloud. Requires the `yc` CLI (tested on 1.30.0) and `jq` on your local machine.

### 1. Add your SSH public key to cloud-init

Open `infra/cloud-init.yaml` and replace the `YOUR_SSH_PUBLIC_KEY_HERE` placeholder under `ssh_authorized_keys` with your own key:

```bash
cat ~/.ssh/id_rsa.pub   # or id_ed25519.pub
```

> The key **must** live inside `cloud-init.yaml` — do not pass `yc compute instance create --ssh-key`. That flag generates its own cloud-config and writes it to the same `user-data` metadata key, so yc rejects the combination outright:
> `ERROR: --ssh-key flag conflicts with user-data metadata key.`

> ⚠️ **Never use `$VARIABLE` inside `cloud-init.yaml`.** `yc` expands environment variables from your **local** shell into the contents of `--metadata-from-file` before uploading it. A variable that is unset locally — such as `$VERSION_CODENAME` — is silently replaced with an empty string, and the VM receives a broken file. Command substitution `$(...)` is passed through untouched and evaluated on the VM, so use `$(lsb_release -cs)` instead. This is why the Docker apt source line in `cloud-init.yaml` uses `$(lsb_release -cs)`.

### 2. Find your subnet name

```bash
yc vpc subnet list
```

### 3. Create the VM

```bash
yc compute instance create \
  --name k8s-news-bot \
  --zone ru-central1-a \
  --cores 8 --memory 8G \
  --create-boot-disk image-folder-id=standard-images,image-family=ubuntu-2204-lts,size=30 \
  --network-interface subnet-name=default-ru-central1-a,nat-ip-version=ipv4 \
  --metadata-from-file user-data=infra/cloud-init.yaml
```

Cloud-init installs Docker Engine + the Compose plugin, `make`, and prepares `/opt/k8s-news-bot`. Creation takes ~45 s; cloud-init then needs a further ~2–3 min to finish installing Docker.

Notes on the flags:
- `--metadata-from-file user-data=...` is how cloud-init is passed. There is no `--cloud-config` flag in `yc`.
- `--network-interface` with `nat-ip-version=ipv4` is required. The public IP is not optional: `yc compute ssh` needs an OS Login profile (which the cloud-init user `yc-user` does not have), and `yc compute scp` does not exist at all — so the VM is reached by plain `ssh`/`scp` over its public IP.
- `--memory 8G` — the flag also accepts a bare `8` (interpreted as GB), but the suffix is unambiguous.
- Substitute the `subnet-name` value with the one from step 2.

### 4. Verify cloud-init actually succeeded

```bash
VM_IP=$(yc compute instance get --name k8s-news-bot --format json \
  | jq -r '.network_interfaces[0].primary_v4_address.one_to_one_nat.address')

ssh yc-user@"$VM_IP" 'docker compose version && docker version --format "{{.Server.Version}}"'
```

> **Do not trust `cloud-init status` alone.** `runcmd` is executed as a plain `#!/bin/sh` script without `set -e`: if the Docker installation fails, the remaining commands still run, the script exits 0, and cloud-init reports `status: done` with `errors: []` — while `final_message` cheerfully prints "Docker installed." The `docker compose version` check above is the only reliable signal, which is why `cloud-init.yaml` also runs it as its last `runcmd` step.

### 5. Deploy project files and start containers

```bash
./infra/deploy.sh
```

The script resolves the VM's public IP via `yc`, copies `news-bot/`, `docker-compose.yml`, `Makefile` and `.env` over `scp`, then builds and starts the stack over `ssh`. Override the defaults with environment variables if needed:

```bash
VM_NAME=my-vm SSH_KEY=~/.ssh/id_ed25519 ./infra/deploy.sh
```

---

## Makefile reference

```
make build        — rebuild Docker image for news-bot
make up           — start all services in background
make down         — stop all services
make logs         — tail all logs (Ctrl+C to exit)
make restart      — rebuild and recreate news-bot container
make test-daily   — run daily digest immediately
make test-weekly  — run weekly report immediately
make status       — show container status
```

---

## Project structure

```
k8s-news-bot/
├── docker-compose.yml          # Three-service stack: ollama + gptr + news-bot
├── Makefile                    # Convenience commands
├── .env.example                # Environment template
├── infra/
│   ├── cloud-init.yaml         # Yandex Cloud VM bootstrap
│   └── deploy.sh               # Deploy script (yc compute scp/ssh)
└── news-bot/
    ├── Dockerfile
    ├── requirements.txt
    └── src/
        ├── main.py             # Entry point, APScheduler setup
        ├── config.py           # Config from env vars
        ├── scheduler.py        # Job functions: daily_digest, weekly_report, cleanup
        ├── delivery/
        │   └── email.py        # Yandex SMTP delivery
        ├── fetchers/
        │   ├── __init__.py     # Article dataclass
        │   └── rss.py          # RSS/Atom fetcher (18 feeds, 8 threads)
        ├── research/
        │   └── gptr.py         # GPT Researcher HTTP client
        └── state/
            └── db.py           # SQLite state (deduplication)
```

---

## Troubleshooting

**First startup hangs at "Waiting for ollama healthy"**
- Ollama is downloading the model (~4 GB). Run `docker compose logs ollama` to see download progress.

**Daily digest runs but email is not received**
- Check `docker compose logs news-bot` for SMTP errors
- Verify `EMAIL_PASSWORD` is an **app password**, not your regular Yandex password
- Check spam folder

**GPT Researcher times out**
- Increase `GPTR_TIMEOUT` in `.env` (e.g. `1800` for 30 minutes)
- mistral:7b on CPU takes 5–15 min per research query; this is normal

**DuckDuckGo returns no results**
- DuckDuckGo rate-limits heavy usage. Wait 10–15 minutes between test runs.
- The RSS section of the digest will still be delivered even if gptr fails.

---

## License

MIT
