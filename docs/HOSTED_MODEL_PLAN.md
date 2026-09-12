# Hosted model plan: qwen3-coder:30b on hardware you rent

Note added 2026-09-07. This document is the plan for the optional second mode: the same bot, unchanged, on a server you rent so a stronger open model is not limited by the machine in front of you. Local mode is the product and stays the default, and nothing here changes what the README claims about it. The plan was written on 2026-09-04 (3862d57), the day after the local rewrite, so it describes the current backend rather than the one the security review examined. It is a plan and not a report: no number in it is measured on rented hardware (the step A and step B speeds say they are estimates, and every measurement in docs/benchmarks/ comes from the laptop), the step B scripts were never exercised against RunPod's API (`scripts/hosted/gpu-up.sh` says so at the top), and step B2 is not built. One change since it was written: on 2026-09-07 the step B1 tunnel example gained the pinned host-key options that `gpu-up.sh` already passed (018e5ba), so the command printed here and the command the script runs now match.

Local is the product. Everything in the README about nothing leaving the machine describes local mode, which stays the default. This document is the optional second mode: the same bot, unchanged, running on a server you rent so that a stronger open model is not blocked by the RAM and disk in front of you. It is private in the sense that matters (the server is yours, the model is open, no provider sees your prompts as a product) and it is not local, which the README will say in as many words.

Prices and figures were gathered on 2026-09-04 and link to their sources. Anything estimated rather than measured says so.

## The one design rule

Ollama has no authentication of its own ([FAQ](https://docs.ollama.com/faq)). Its API port is never exposed to the internet, in either step below. The backend and Ollama sit on loopback on the same box, or the backend reaches a remote Ollama through an SSH tunnel that presents as loopback. The only thing on a public port is `/webhook/github` behind TLS, exactly as at home. `STRICT_LOCAL` stays `true` and its loopback check stays literally true. A public Ollama was the CVE-2026-7482 story: an unauthenticated memory leak, about 300,000 exposed servers, fixed in 0.17.1 ([Qualys](https://threatprotect.qualys.com/2026/05/11/ollama-heap-out-of-bounds-read-vulnerability-leads-to-remote-process-memory-leak-cve-2026-7482/)). We pin 0.33.1.

## Options, with the numbers

Sizing: about 8k prompt and 1.2k output tokens per file, four files per PR, three PRs a day. Per-review costs are calculated from those assumptions, not quoted by vendors.

| Shape                                                                                                                                                    | Always-on cost                                                            | Per review                                                  | Generation speed                                                                                                                                            | Effort                                             | Privacy                                                   |
| -------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- | ----------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- | --------------------------------------------------------- |
| A. All-in-one CPU box: [Netcup RS 4000 G12](https://netcupvoucher.com/blog/netcup-pricing-2026), 12 dedicated EPYC 9645 cores, 32 GB DDR5 ECC, 1 TB NVMe | €33.55/month                                                              | about €0.37 at 3 PRs a day, falling with volume             | 8 to 20 tok/s (estimate; [a 64-core EPYC measured 43 tok/s](https://ahelpme.com/ai/llamacpp-ai/llama-bench-the-qwen3-coder-30b-a3b-and-amd-epyc-9554-cpu/)) | Low                                                | Your box, Ollama on loopback                              |
| B. Small always-on VPS for the backend plus a [RunPod](https://www.runpod.io/pricing) RTX A5000 24 GB pod started per review                             | VPS €5 to €10 (to confirm) plus about $2/month for a 30 GB network volume | about $0.04 at $0.16 to $0.27 per hour                      | 60 to 110 tok/s (estimate)                                                                                                                                  | High: start and stop, one to two minute cold start | Rented GPU, container on their hardware, reached over SSH |
| C. [Hetzner GEX45](https://www.hetzner.com/dedicated-rootserver/matrix-gpu/) dedicated, RTX PRO 4000 24 GB, 64 GB RAM                                    | €214/month plus €209 setup                                                | about €2.38                                                 | 60 to 110 tok/s (estimate)                                                                                                                                  | Medium                                             | Dedicated, EU                                             |
| D. [OpenRouter](https://openrouter.ai/qwen/qwen3-coder-30b-a3b-instruct), comparison only                                                                | none                                                                      | $0.0036 ($0.07 per million input, $0.27 per million output) | provider-side                                                                                                                                               | Lowest                                             | Your code leaves your control; not this project's point   |

Ruled out: Hetzner cloud CPU servers (prices [more than doubled on 2026-06-15](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/)); any 20 GB card such as the Hetzner GEX44, because 19 GB of Q4 weights plus a 16k KV cache does not fit; Contabo's cheaper 48 GB plan only on a 24-month term; smee-style relays; Ollama's own cloud models, which are a hosted service ([pricing](https://ollama.com/pricing), no-logging terms stated) and would not be your hardware.

Recommendation: step A first. It is the fully local architecture on rented hardware, fixed cost, no orchestration, and it can be set up in an afternoon. Add step B on top when the wait becomes annoying. Do not start with B: an on-demand box that is off cannot receive a webhook, and GitHub does not retry deliveries on its own ([best practices](https://docs.github.com/en/webhooks/using-webhooks/best-practices-for-using-webhooks)), so something cheap must always be listening.

## Step A: the all-in-one box

Everything on one server. Ollama on loopback, the backend on loopback, Caddy on 443 forwarding only the webhook path, the dashboard on loopback reached through SSH. Ollama and the backend never see the internet directly.

### A1. Order and harden

1. Order the Netcup RS 4000 G12 with Ubuntu 24.04 LTS. Add your SSH public key during setup.
2. First login as root, then:

```
adduser reviewbot && usermod -aG sudo reviewbot
rsync -a ~/.ssh /home/reviewbot/ && chown -R reviewbot:reviewbot /home/reviewbot/.ssh
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/; s/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
systemctl restart ssh
apt update && apt upgrade -y && apt install -y ufw caddy git python3-venv build-essential autossh sqlite3
curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && apt install -y nodejs   # Node 22 with npm at /usr/bin/npm, which the dashboard unit assumes
ufw default deny incoming && ufw default allow outgoing
ufw allow 22/tcp && ufw allow 80/tcp && ufw allow 443/tcp && ufw enable
```

3. Unattended security updates: `apt install -y unattended-upgrades && dpkg-reconfigure -plow unattended-upgrades`.

Optional second fence on 443: allow only GitHub's webhook source ranges from `curl -s https://api.github.com/meta | jq .hooks` (on 2026-09-04: `192.30.252.0/22`, `185.199.108.0/22`, `140.82.112.0/20`, `143.55.64.0/20`, `2a0a:a440::/29`, `2606:50c0::/32`). GitHub says an allow list can block spoofed requests but does not recommend relying on it, and the ranges change, so re-read `/meta` monthly. The HMAC check is the real gate; this is extra.

### A2. Ollama, pinned and on loopback

```
curl -fsSL https://ollama.com/install.sh | OLLAMA_VERSION=0.33.1 sh
sudo systemctl edit ollama
```

Paste into the override:

```
[Service]
Environment=OLLAMA_HOST=127.0.0.1:11434
Environment=OLLAMA_NO_CLOUD=1
Environment=OLLAMA_KEEP_ALIVE=30m
Environment=OLLAMA_NUM_PARALLEL=1
Environment=OLLAMA_MAX_LOADED_MODELS=1
Environment=OLLAMA_FLASH_ATTENTION=1
Environment=OLLAMA_KV_CACHE_TYPE=q8_0
```

Then `sudo systemctl daemon-reload && sudo systemctl restart ollama`, `ollama pull qwen3-coder:30b` (19 GB, once), and measure before trusting any estimate in this document:

```
ollama run qwen3-coder:30b --verbose "Explain in three sentences what a SQL injection is."
```

The eval rate it prints is the generation speed for this box. Also note the prompt eval rate: a review is prefill-heavy, and prefill on CPU is the slow part. Check `ss -ltnp | grep 11434` shows only 127.0.0.1.

### A3. The backend

```
sudo -iu reviewbot
git clone <your fork> reviewbot && cd reviewbot/backend
python3 -m venv .venv && .venv/bin/pip install --require-hashes -r requirements.lock
cp .env.example .env
```

The lock carries hashes for every wheel of each pinned version, so it installs on Ubuntu's Python 3.12 as well as 3.13; if pip reports a hash mismatch, regenerate the lock on the box with `pip-compile --generate-hashes` in a scratch venv.

`.env` differs from the laptop in these lines only:

```
OLLAMA_MODEL=qwen3-coder:30b
OLLAMA_NUM_CTX=16384
OLLAMA_TIMEOUT_SECONDS=1200
REVIEW_TIMEOUT_SECONDS=3600
MAX_FILES_PER_REVIEW=10
ALLOWED_HOSTS=localhost,127.0.0.1,reviewbot.yourdomain.example
GITHUB_PRIVATE_KEY=/home/reviewbot/.config/reviewbot/github-app.pem
```

Copy the App's private key up with `scp` into that path and `chmod 600` it. The longer timeouts and the lower file cap are for CPU speed; raise the cap once the measured speed says you can.

Systemd unit `/etc/systemd/system/reviewbot-backend.service` (a copy is in `scripts/hosted/`):

```
[Unit]
Description=ReviewBot backend
After=network-online.target ollama.service
Wants=ollama.service

[Service]
User=reviewbot
WorkingDirectory=/home/reviewbot/reviewbot/backend
ExecStart=/home/reviewbot/reviewbot/backend/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/home/reviewbot/reviewbot/backend

[Install]
WantedBy=multi-user.target
```

`sudo systemctl enable --now reviewbot-backend`, then `journalctl -u reviewbot-backend -f` should show the model name and the loopback bind. `curl -s http://127.0.0.1:8000/health` answers.

### A4. Caddy: TLS, and only the webhook path

Point a DNS A record (and AAAA if the box has IPv6) at the server. `/etc/caddy/Caddyfile`:

```
reviewbot.yourdomain.example {
    handle /webhook/github {
        reverse_proxy 127.0.0.1:8000
    }
    handle {
        respond 404
    }
}
```

`sudo systemctl reload caddy`. Caddy fetches and renews the certificate itself. Everything except the webhook path (with or without a trailing slash) answers 404 at the edge, so `/health` and the dashboard API are not reachable from outside at all. If a delivery shows red with a 404 and nothing in the backend log, the App's webhook URL does not match the path Caddy forwards; it must be exactly `https://reviewbot.yourdomain.example/webhook/github`.

Change the GitHub App's webhook URL to `https://reviewbot.yourdomain.example/webhook/github`, save, and Redeliver the ping. It should be green.

### A5. The dashboard, through SSH

On the box: `cd ~/reviewbot && npx npm@11 ci && npm run build`, `.env.local` with the backend URL and token, and a second unit (also in `scripts/hosted/`) running `npm run start` on 127.0.0.1:3000. From your laptop:

```
ssh -N -L 3000:127.0.0.1:3000 reviewbot@reviewbot.yourdomain.example
```

and open http://127.0.0.1:3000. The dashboard's own Host check accepts it because the request arrives on loopback.

### A6. What to expect, honestly

A six-file PR at the estimated CPU speed is fifteen to forty minutes of wall time, most of it prefill. The webhook still answers GitHub in milliseconds, the queue holds the work, and a second push supersedes the first job, so nothing is lost; it is simply slow. Measure with A2 before deciding whether that is acceptable. The SQLite database is the only state worth backing up, and it runs in WAL mode, so copying `reviews.db` alone misses committed rows still in `reviews.db-wal`. Back it up with `sqlite3 backend/reviews.db ".backup /path/to/backup.db"` while the service runs, or stop `reviewbot-backend` and copy `reviews.db`, `reviews.db-wal` and `reviews.db-shm` together.

Keep Ollama pinned. Upgrade on purpose, after reading the release notes, never automatically.

## Step B: pay-per-use GPU, on top of step A

Keep the backend where it is (the Netcup box, or any small VPS). Put Ollama and the model on a RunPod pod that only runs while reviewing.

### B1. Manual, today

1. RunPod account, then a Network Volume of 30 GB in one region ($0.07 per GB per month, about $2.10; [pricing](https://www.runpod.io/pricing)). Weights live on the volume, so a stopped pod costs only the volume. A stopped pod's own container disk is billed at the higher idle rate, so keep it small.
2. Create a pod from the `ollama/ollama:0.33.1` image on an RTX A5000 24 GB (community cloud from $0.16 per hour, secure cloud $0.27), with the network volume mounted at `/root/.ollama`, `OLLAMA_HOST=127.0.0.1:11434`, SSH enabled, and no HTTP port exposed. First start: `ollama pull qwen3-coder:30b` once; it lands on the volume.
3. Stop the pod. Note its id, its SSH host and port from the pod's Connect panel, and install `runpodctl` on the backend box with your API key. Pin the pod's SSH host key once, because the host and port change between starts and the tunnel is the only thing standing between your diffs and whoever answers on that address: on the backend box run `ssh-keyscan -p <port> <host> | sed 's/^[^ ]* /reviewbot-gpu-pod /' >> ~/.config/reviewbot/gpu-pod.known_hosts`, then compare `ssh-keygen -lf ~/.config/reviewbot/gpu-pod.known_hosts` with the fingerprint RunPod's panel shows before trusting it. `gpu-up.sh` refuses to start without that pin and refuses a pod whose key does not match it; re-pin only when you recreate the pod.
4. The scripts restart the backend with `sudo systemctl restart`, so the operator needs a passwordless sudo rule for exactly that: `echo "reviewbot ALL=(root) NOPASSWD: /usr/bin/systemctl restart reviewbot-backend" | sudo tee /etc/sudoers.d/reviewbot-restart` and `chmod 440` it. Then, on the backend box, `scripts/hosted/gpu-up.sh <pod-id> <ssh-host> <ssh-port>`: starts the pod, waits for SSH, opens `autossh -M 0 -N -o StrictHostKeyChecking=yes -o UserKnownHostsFile=~/.config/reviewbot/gpu-pod.known_hosts -o HostKeyAlias=reviewbot-gpu-pod -L 11435:127.0.0.1:11434 -p <port> root@<host>` (the pinned options, as `gpu-up.sh` passes them), waits until `http://127.0.0.1:11435/api/tags` lists the model, then restarts the backend with `OLLAMA_BASE_URL=http://127.0.0.1:11435` and `OLLAMA_MODEL=qwen3-coder:30b`. `gpu-down.sh` reverses it. Both scripts are written but were not exercised against RunPod's API when this document was written; they say so at the top.
5. The backend's loopback check is satisfied because the URL is loopback; the bytes go through SSH to the pod. Local Ollama on the box keeps port 11434, so both modes can coexist and a `.env` line chooses.

Cost per review: a review that keeps the pod up for ten minutes including a ninety-second cold start costs about $0.03 to $0.05 on an A5000. Ten reviews a day is about $0.40 a day plus the volume; with a fifteen-minute idle timer per burst (phase B2) count on about $1 a day.

### B2. Automatic, later

A `MODEL_HOST=runpod` setting; the queue worker calls `ensure_running()` before the first job of a burst and an idle timer calls `stop()` after, say, fifteen minutes; RunPod's REST API replaces `runpodctl`. Tests: a fake RunPod API for start, stop, a start that fails, and a tunnel that never comes up (the job must fail cleanly and the delivery must accept redelivery). Docs: the Status page shows the pod state. Not built until B1 has been used by hand for a while.

## What changes in the README for hosted mode

- "Nothing leaves the machine" becomes "in local mode, nothing leaves the machine". In hosted mode the diff is processed on a server you rent; in step B it also travels over SSH to a GPU rented by the hour, where the provider could in principle read the container's memory. Nothing is retained by design on either.
- The Status page shows the model address (`OLLAMA_BASE_URL`, reported by `/api/status`), so a box configured for step B shows the tunnel port rather than 11434.
- The permissions, the App, the redaction, the sanitiser, the queue and the dashboard are identical in both modes. Only the model's address and its name change.

## Cost worksheet

| Item                       | Local (laptop) | Step A                        | Step A plus B                                |
| -------------------------- | -------------- | ----------------------------- | -------------------------------------------- |
| Fixed monthly              | 0              | €33.55                        | €33.55 plus about $2                         |
| Per review                 | electricity    | included                      | about $0.04                                  |
| Ten reviews a day, a month | 0              | €33.55                        | about €46                                    |
| Speed                      | 33 tok/s (9B)  | 8 to 20 tok/s (30B, estimate) | 60 to 110 tok/s (30B, estimate)              |
| Reads your code            | nobody else    | your host, in principle       | your host and the GPU provider, in principle |
