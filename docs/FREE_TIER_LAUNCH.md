# Launching Flatmate for ₹0 (student plan)

This is the complete procedure for running Flatmate in production with no money and no credit
card, using free student offers. Every step is here, in order. The steps that need you (making
accounts, proving you're a student, accepting terms, choosing passwords) are marked
**You**; everything else is automated by scripts and GitHub Actions in this repository.

Read section 1 first: it says honestly what this setup can and can't do.

## 1. What you get, and the honest limits

```mermaid
flowchart LR
    U[People's browsers] -->|"HTTPS: your-domain (website), api.your-domain (API + WebSocket)"| C
    subgraph VM [Azure VM, 2 vCPU / 1 GiB, free for 12 months]
        C[Caddy<br/>automatic HTTPS] --> N[Website<br/>Next.js server]
        C --> A[API<br/>2 processes]
        N -->|listing pages, private network| A
        W[Worker<br/>jobs + weekly ML training] --> R[(Redis<br/>queue, cache, limits)]
        A --> R
    end
    A -->|pooler, port 6543| S[(Supabase Free<br/>Postgres, file storage)]
    W --> S
    GH[GitHub Actions] -->|build, migrate, deploy, roll back| VM
    GH -->|nightly verified backup| B[(Azure Blob<br/>private, 30 days)]
    GH -->|every 10 min| UP{{uptime check}}
```

| Part | Service and plan | Cost | Free for |
|---|---|---|---|
| Website, API, worker, Redis, HTTPS | Azure for Students: B2ats v2 VM, 64 GB SSD | ₹0 (12-month free VM; the $100 credit covers the public IP) | 12 months, renewable yearly while a student |
| Database, file storage | Supabase Free | ₹0 | Always (paused after 7 days with no traffic; the uptime check prevents that) |
| Images (Docker) | GitHub Container Registry | ₹0 | Always for a public repository |
| CI/CD, uptime checks | GitHub Actions | ₹0 | Always for a public repository |
| Backups | Azure Blob (private) | ₹0 (5 GB free) | 12 months |
| Email | Brevo Free (300 emails a day) | ₹0 | Always |
| Error tracking | Sentry (Student Pack) | ₹0 | 1 year, renewable |
| Domain | Name.com (.live, .studio, ...), .TECH or Namecheap .me (Student Pack) | ₹0 | 1 year (then about ₹800–2,500 a year) |
| Search and matching AI | Built in (local embeddings, ranking models trained weekly) | ₹0 | Always |

**What it can carry.** The code is the same as the 10,000-user design (docs/CAPACITY_PLAN.md):
overload gets a quick "busy, retry" answer instead of a crash, and the web app retries for you.
The hardware is not, though:
- **The VM's stack was measured with 600 people at once** (section 15): no errors, the slowest
  5% of requests within 21 ms, using about 660 MiB of its 1 GiB.
- **Supabase Free** (shared CPU, 500 MB RAM, 500 MB data) will run out first. Plan on a few
  hundred to about a thousand people at once, then upgrade it.

10,000 people at once needs the paid plan in docs/CAPACITY_PLAN.md: no free plan anywhere can
do that.

**What's turned off, and why:**

| Off | Why | Turn it on when |
|---|---|---|
| Phone verification by SMS | Twilio costs money. The app hides it (`SMS_PROVIDER=disabled`). | You can pay for SMS (Twilio, with DLT registration for India). |
| Paid plans | Live Razorpay needs a registered business. Everything is free for users meanwhile. | You have a business and KYC; see E6 in LAUNCH_GAP_LIST.md. |
| AI moderation and smart replies (Claude) | They need a paid Anthropic key. Rule-based moderation still runs. | Set `PRODUCTION_ANTHROPIC_API_KEY`. |
| Virus scanning of uploads (ClamAV) | It needs about 1 GB more RAM than the VM has. Uploads are still checked for type and size. | You move to a bigger server (E8). |

**One rule to keep:**
- **Free offers expire:**
  - the Azure free VM after 12 months;
  - the domain after 1 year;
  - the backup link after 1 year.

  Section 13 lists the dates to write down.

## 2. Accounts (You)

Use one email for everything if you can. Turn on two-factor sign-in on every account; section 12
says why.

1. **GitHub Student Developer Pack:** <https://education.github.com/pack>, "Sign up for Student
   Developer Pack".
   - Verify with your college email, or upload your student ID card when asked.
   - Approval can take a few days.
   - It gives you GitHub Pro, the Azure offer, Sentry's student plan, a free domain and more.
2. **Azure for Students:** <https://azure.microsoft.com/free/students>, "Start free".
   - Sign in with a Microsoft account and verify with your college email (or through the GitHub
     pack).
   - **No credit card.**
   - It has a spending limit: when the $100 credit is used up, things stop. Nothing is ever
     billed to you.
3. **Supabase:** you already have the project. Keep it on the Free plan.
4. **Brevo** (email): <https://www.brevo.com>, free plan, no card.
5. **Sentry** (optional, recommended): through the GitHub Student Pack offer page.
6. **A domain:** claim one free for a year through the Student Pack:
   - Name.com: <https://www.name.com/partner/github-students> (.live, .studio, .app, ...);
   - get.tech (.tech) or Namecheap (.me) through the pack's offer pages.

   The website and the API both run on the VM under it: `<your-domain>` and
   `api.<your-domain>`.

## 3. Lock down Supabase first (You, 10 minutes)

These are the still-open launch items E1 (steps 2 and 4) and E2b. A key and the database
password were pasted into chats, so replace them before going live. The new values go only into
your git-ignored `.env.free-tier` (step 6), never into a chat, email or tracked file.

1. **New secret key** (E1 step 2):
   1. Go to Supabase dashboard → Project Settings → API Keys.
   2. Create a new secret key and put it in `SUPABASE_SECRET_KEY`.
   3. Delete the old `sb_secret_...` key once the first deploy is live.
2. **New database password** (E1 step 4):
   1. Go to Project Settings → Database → Reset database password.
   2. Use the generator, and put the password in `SUPABASE_DB_PASSWORD`.
   3. Also update `apps/api/.env` if you still use it.
3. **The pooler host:** go to Project Settings → Database → Connect → "Session pooler" and put
   the host (`aws-N-<region>.pooler.supabase.com`) in `SUPABASE_POOLER_HOST`.
   - On the free plan the direct address (`db.<ref>.supabase.co`) works only over IPv6, which
     GitHub and Azure don't use.

`scripts/production_setup.py` builds the connection URLs from these and percent-encodes the
password:

| Used for | GitHub secret | User | Port |
|---|---|---|---|
| Migrations, backups, making the first admin (owner) | `PRODUCTION_DATABASE_URL`, `BACKUP_DATABASE_URL` | `postgres.<ref>` | 5432 (session pooler) |
| The running API and worker (least privilege) | built by each deploy from `PRODUCTION_APP_DB_PASSWORD` | `flatmate_api.<ref>` | 6543 (transaction pooler) |

## 4. Create the server, backups and the API's database login (You start it; the script does the rest)

Everything here runs in **Azure Cloud Shell**, a free Linux terminal in your browser that's
already signed in to Azure. Nothing needs installing on your computer.

1. Open <https://portal.azure.com> and click the `>_` icon at the top. Choose **Bash**. If asked,
   create the small storage it needs: that's free within the student offer.
2. Sign in to GitHub from Cloud Shell, so the script can save secrets for you:

   ```bash
   gh auth login        # GitHub.com → HTTPS → "Login with a web browser", then follow the code
   ```
3. Get the code and run the setup. Pick a `DNS_LABEL`: lowercase letters, digits and hyphens,
   unique in the region. It becomes `<DNS_LABEL>.<region>.cloudapp.azure.com`.

   ```bash
   git clone https://github.com/AMIYA8597/livora.git && cd livora
   DNS_LABEL=livora-api bash infrastructure/free-tier/provision-azure.sh
   ```

   It takes 5–10 minutes and:
   - **creates the VM:** Ubuntu 24.04, 2 vCPU, 1 GiB, 64 GB SSD. It tries the Indian regions
     first, then others your student subscription allows.
   - **hardens it on first boot:**
     - SSH by key only, no root login, fail2ban;
     - firewall open only for 22, 80 and 443;
     - automatic security updates;
     - 2 GiB swap;
     - Docker.
   - **creates backup storage:** a private container whose backups are deleted after 30 days,
     plus a **create-only** link for the backup job.
   - **makes a deploy key** that never leaves Cloud Shell and GitHub.
   - **saves the connection details as GitHub secrets:** `FREE_TIER_HOST`, `FREE_TIER_SSH_KEY`,
     `FREE_TIER_SSH_KNOWN_HOSTS` and `BACKUP_AZURE_SAS_URL`.

   If it says no region allowed the VM, run it again with the regions your subscription allows
   (Azure portal → Policy → "Allowed locations"), for example
   `REGIONS="eastus westeurope" DNS_LABEL=... bash ...`.
4. The API's own database login (E2b) is automatic.
   - **What it is:** it can read and write app data through row-level security, but it can't
     change the schema or bypass security.
   - **How it's made:** every deploy creates or updates it from `PRODUCTION_APP_DB_PASSWORD`
     (`scripts/app_db_login.py`), which step 6 generates.
   - **The password stays out of logs:** it's sent to the database only as a SCRAM hash, so it
     never appears in a SQL statement or the database's logs.

## 5. Point the domain at the server (You, 5 minutes)

In your registrar's DNS settings (Name.com → My Domains → the domain → Manage DNS Records), add
three `A` records, each to the IP address the script printed (Azure portal → the VM → Public IP
address):

| Type | Host | Answer | TTL |
|---|---|---|---|
| A | *(empty, or `@`)* | the VM's IP | 300 |
| A | `www` | the VM's IP | 300 |
| A | `api` | the VM's IP | 300 |

- Delete any parking records the registrar added for the same names (an `ALIAS`, `CNAME` or `A`
  for `@` or `www`).
- With Cloudflare instead, keep the records **DNS only** (grey cloud), so Caddy can get its
  certificates and sees real client addresses.
- Wait until `nslookup <your-domain>`, `nslookup www.<your-domain>` and
  `nslookup api.<your-domain>` all show the IP (minutes, sometimes an hour).

Then in step 6, `API_DOMAIN` is `api.<your-domain>` and `WEB_URL` is `https://<your-domain>`.
Caddy gets the certificates for all three names by itself on the next deploy.

**Without a domain** the API still works at the `cloudapp.azure.com` address the script printed,
but the VM serves no website.

## 6. GitHub settings (You fill one file; one command sets everything)

1. Copy `infrastructure/free-tier/free-tier.env.example` to `.env.free-tier` at the repository
   root. Git ignores that name.
2. Fill it in: the Supabase values from step 3, the addresses from step 5, and Brevo from
   step 7. Never paste these values into a chat.
3. On your computer, signed in with `gh auth login`, run:

   ```bash
   python scripts/production_setup.py --dry-run   # names only: what it would set
   python scripts/production_setup.py
   ```

It sets these, printing names only. Values go to `gh` over stdin:
- **Secrets:**
  - `PRODUCTION_DATABASE_URL` and `BACKUP_DATABASE_URL`: the owner login, on the session pooler.
  - `PRODUCTION_SUPABASE_SECRET_KEY`.
  - `PRODUCTION_SMTP_PASSWORD`, `PRODUCTION_SENTRY_DSN` and `PRODUCTION_ANTHROPIC_API_KEY`, when
    you fill them in.
  - `PRODUCTION_SECRET_KEY` and `PRODUCTION_APP_DB_PASSWORD`: generated. Nobody ever needs to
    know them.
- **Variables:**
  - `API_DOMAIN`, `WEB_DOMAIN` (from `WEB_URL`), `ACME_EMAIL`, `UPTIME_API_URL` and
    `UPTIME_WEB_URL`.
  - `RUNTIME_ENV`, the app's non-secret settings: the website address and CORS, the Supabase
    URLs, and the Brevo login and sender.

Run it again after changing the file:
- It keeps the two generated secrets, so nobody is signed out.
- `--rotate` makes new ones.
- Empty lines are skipped, not cleared.

The deploy adds the free-tier defaults by itself (scripts/compose_env.py), and anything in
RUNTIME_ENV overrides them:
- 2 API processes;
- a small database pool (20 connections at most);
- overload limits;
- `SMS_PROVIDER=disabled`;
- local embeddings;
- Supabase storage.

Secrets are refused in RUNTIME_ENV.

## 7. Email with Brevo (You, 5 minutes)

1. Go to Brevo → Senders, Domains & Dedicated IPs → **Senders** and add the address you'll send
   from, then confirm it.
2. With a domain, also go to **Domains**, add yours and create the DNS records Brevo shows
   (SPF, DKIM, DMARC). Mail then reaches inboxes, not spam.
3. Go to Brevo → SMTP & API → **SMTP**. The login goes in `RUNTIME_ENV` as `SMTP_USERNAME`;
   generate an SMTP key for `PRODUCTION_SMTP_PASSWORD`.

The free plan sends 300 emails a day. The app emails only password resets, application and
appointment updates, and unread-chat reminders (at most one an hour per chat).

The app checks the SMTP server's certificate before sending the password.

## 8. First deploy (automatic from here)

```bash
gh variable set FREE_TIER_ENABLED -b true
gh workflow run "Free-tier Deployment"
gh run watch
```

The **Free-tier Deployment** workflow:
1. builds the API image and the website's image and pushes them to `ghcr.io`. The website's
   addresses are compiled into it, so its tag includes a hash of them;
2. takes a verified backup of the database (dump, restore into a throwaway database, compare)
   and stores it in your private Azure container;
3. applies the database migrations;
4. writes the app's settings from your secrets (it prints names only, never values);
5. copies the stack to the VM and starts it. Caddy gets the HTTPS certificates, and if the
   new release (API and website) isn't healthy within 3 minutes, the previous one is put back
   and the run fails;
6. checks from outside: `https://<API_DOMAIN>/health/ready`, the website, that the API's CORS
   allows exactly the website, and that `www.` redirects to the bare domain.

After this, **every push to `main` that passes CI deploys itself.** Every change to the server
setup is also tested first by **Free-tier Stack Test**, which runs the same stack on GitHub's
machines with the VM's limits:
- deploy, and rollback from a broken release;
- HTTPS and the security headers, for the API and the website;
- the website rendering a listing from the API;
- the ports that are reachable from outside;
- a 3-minute load test on the API while people browse the website, with no out-of-memory and
  no server errors allowed.

Check it yourself:

```bash
curl https://<API_DOMAIN>/health/ready          # {"status":"ready", ... "database":{"status":"ok"}, "redis":{"status":"ok"}}
curl https://<API_DOMAIN>/api/v1/meta/app-config  # "features":{"phone_verification":false,"payments":false}
curl -I https://<your-domain>/                     # 200, with Content-Security-Policy and Strict-Transport-Security
curl -I https://www.<your-domain>/                 # 308 to https://<your-domain>/
```

## 9. The website (automatic)

The VM serves the website (`infrastructure/docker/Dockerfile.web`, a standalone Next.js server)
next to the API, behind the same Caddy:
- **Built per deploy** with the public addresses compiled in:
  - `NEXT_PUBLIC_API_URL=https://<API_DOMAIN>/api/v1`;
  - `NEXT_PUBLIC_APP_URL=https://<WEB_DOMAIN>`;
  - `ENVIRONMENT=production`, which lets search engines index it.
- **Listing pages and the sitemap** fetch from the API container directly (`API_INTERNAL_URL`),
  never over the internet.
- **Locked down the same way as the API:** read-only, unprivileged, no Linux capabilities, a
  256 MB memory cap, and reachable only through Caddy.
- **Chat** connects to `wss://<API_DOMAIN>`; the site's security policy allows exactly the
  API's address.
- **Browser error tracking (optional):** set the repository variable `WEB_SENTRY_DSN` to a
  Sentry project's public DSN.

To change the domain later: update `WEB_URL` and `API_DOMAIN` in `.env.free-tier`, rerun step 6,
and run the deploy. Without `WEB_DOMAIN`, the deploy runs no website on the VM.

## 10. First admin (You, 5 minutes)

This is launch item E12.
1. Sign up on the live site with your own email.
2. In Cloud Shell, in the `livora` folder:

   ```bash
   python3 -m venv ~/fm && ~/fm/bin/pip install -q -e apps/api -c apps/api/constraints.txt
   read -rsp "Owner URL: " DATABASE_URL; echo; export DATABASE_URL
   ~/fm/bin/python scripts/grant_role.py --email you@example.com --role super_admin
   unset DATABASE_URL
   ```
3. Sign out and back in. The admin console (`/admin`) now opens, with the **Traffic** tab for
   live load.
4. Appoint any other staff from the console. Nobody can sign up as staff.

## 11. The AI and ML parts (automatic)

These are all free and run on the VM:
- **Search and "similar listings":** text embeddings computed in-process
  (`EMBEDDING_PROVIDER=local`: hashed word and character n-grams, typo-tolerant, no API calls).
  New and edited listings and profiles are indexed automatically. To index existing data
  once, for example after a restore:

  ```bash
  ssh -i ~/.ssh/flatmate_deploy deploy@<FREE_TIER_HOST> \
    'cd /opt/flatmate && docker compose exec worker python -m app.ml.cli backfill-embeddings'
  ```
- **Flatmate matching:** a compatibility score from lifestyle, budget, location and habits.
- **Ranking:** two learning-to-rank models (people and listings) are retrained every Monday
  night by the worker once there's enough interaction data (`RANKER_MIN_TRAINING_ROWS`, 200).
  Until then the hand-tuned weights are used. The models are stored in the database
  (`ml_models`), so a redeploy never loses them.
- **Moderation:** rule-based checks always run. Claude-based moderation and smart replies
  switch on when you set `PRODUCTION_ANTHROPIC_API_KEY` (paid).
- **Better semantic search, later:** `EMBEDDING_PROVIDER=voyage` with
  `PRODUCTION_VOYAGE_API_KEY`. Its free tokens come with low rate limits, so keep `local`
  until you can pay.

## 12. Security (what's enforced, and what you must do)

**Already enforced by this setup:**
- **The VM:**
  - SSH keys only, no root, fail2ban;
  - firewall: 22, 80 and 443 only;
  - automatic security updates with a nightly reboot when needed.
- **The containers:**
  - read-only filesystems, all Linux capabilities dropped, `no-new-privileges`, a non-root
    user, a memory cap each;
  - Redis isn't reachable from outside and needs a password generated on the VM.
- **HTTPS everywhere:** an automatic Let's Encrypt certificate, HSTS, the `Server` header
  removed, and requests over 20 MB refused at the edge.
- **The app:**
  - security headers and CSP;
  - rate limits per IP and per account;
  - bcrypt passwords;
  - overload protection;
  - request ids for tracing.
- **The database:**
  - row-level security on every table (checked: 54 tables, 54 policies);
  - the API uses a least-privilege login with a 15 s statement timeout;
  - the owner login is used only by migrations and backups.
- **Secrets:**
  - only in GitHub encrypted secrets and the VM's `api.env` (mode 600);
  - logs print names, never values;
  - the deploy key and registry token are deleted after each run;
  - the backup link can only create files, never read or delete.
- **Backups:** nightly and verified by a real restore, kept 30 days in private storage.

**You must:**
1. **Turn on two-factor sign-in** for GitHub, Microsoft (Azure), Supabase, Brevo and your
   domain registrar. Whoever gets into one of these gets into production.
2. **Protect `main`:**
   - GitHub → Settings → Branches → add a rule for `main`;
   - require the CI checks to pass;
   - block force pushes.
3. **Turn on security scanning:**
   - GitHub → Settings → Code security: Dependabot alerts and security updates, secret
     scanning and push protection (free for public repositories);
   - finish E1 step 6: mark the old `f9ad144` finding as handled.
4. **Keep secrets out of chats, screenshots and commits.** If one leaks, rotate it (Supabase
   key and password: step 3; `PRODUCTION_SECRET_KEY`: set a new one, after which everyone signs
   in again).
5. **Get a legal review** of the privacy page and the DPDP rights card before real users join
   (E9). Universities often have free legal aid clinics.

## 13. Running it day to day

| Task | How |
|---|---|
| Deploy | Push to `main`. CI runs, then the deploy runs. |
| Roll back | Actions → Free-tier Deployment → Run workflow, with an older commit as `ref` |
| See live traffic | Admin console → Traffic, or Azure portal → the VM → Monitoring |
| Read logs | `ssh -i ~/.ssh/flatmate_deploy deploy@<host> 'cd /opt/flatmate && docker compose logs --tail 200 web api worker'` |
| Restart | `ssh ... 'cd /opt/flatmate && docker compose restart web api worker'` |
| Uptime alerts | Automatic: the Uptime workflow checks every 10 minutes, and GitHub emails you when it fails |
| Error alerts | Sentry emails you new errors (set an alert rule in Sentry) |
| Backups | Nightly at 03:00 IST (Database Backup workflow). To restore, see `scripts/db_backup.py restore`; it only restores into a new, empty database. |
| Practise a restore | Every 3 months: restore the latest backup into a new local database and check that the manifest matches |

**Dates to write in your calendar** (from the day you run step 4):
- **after 11 months:**
  - the free VM ends at 12 months: renew Azure for Students, then decide whether to keep the
    VM on credit or move it;
  - run `provision-azure.sh` again to renew the 1-year backup link.
- **after 11 months:** renew the domain (Name.com sends a reminder), or the site goes offline
  when it expires.
- **every year:** renew Azure for Students and Sentry's student plan, and re-verify the
  GitHub pack when asked.

## 14. Costs: how to stay at ₹0

- Azure for Students can't charge you: when the credit runs out, things stop.
- **Check the meter:** Azure portal → Subscriptions → Azure for Students → Credits shows what's
  used. The VM, disk, backups and bandwidth are within the free amounts. The public IP uses
  about $3–4 of credit a month.
- **Don't change the VM size:** larger sizes aren't free.
- **Don't add services by clicking around in the portal**, unless the page says it's free.
- **Supabase Free:**
  - watch Database size (500 MB) and Egress (5 GB a month) in Reports;
  - most egress is photos: the website caches resized images, which keeps it low.

## 15. Capacity, and when to upgrade

The **Free-tier Stack Test** measures the stack on every change with the VM's limits
(2 vCPU, 1 GiB) and writes the results in its run summary. To try more people, run it by hand
(Actions → Free-tier Stack Test → Run workflow) with a higher `users`.

Measured on 2026-11-26. Each run lasts 3 minutes of real browsing (visitors, signed-in members
and sign-ins), through HTTPS and Caddy:

| People at once | Requests | Failed | Median | Slowest 5% | Slowest 1% | Peak memory: API, worker, Caddy, Redis |
|---|---|---|---|---|---|---|
| 150 | 4,293 (24 a second) | 0 | 8 ms | 33 ms | 190 ms | 384, 214, 36, 12 MiB |
| 600 | 15,147 (85 a second) | 0 | 5 ms | 21 ms | 64 ms | 403, 150, 61, 12 MiB |

The test's database is a container on GitHub's machine, not Supabase Free. Supabase Free's shared
CPU and 500 MB RAM will be the limit before the VM is.

Upgrade when the Traffic tab shows the stack under strain for long stretches:
- **"Strained" or "Busy":** many 503s, the slowest 5% of requests above 1 s, or database
  connections near the limit;
- **Supabase Reports:** CPU near 100%.

In order of cost:
1. **Supabase Pro** (about ₹2,100 a month): dedicated CPU, daily backups, no pausing.
2. **A bigger VM** paid from Azure credit or a startup programme (Microsoft for Startups,
   Google for Startups and AWS Activate give $1,000s to new founders).
3. **The full plan for 10,000 people at once** (docs/CAPACITY_PLAN.md): Cloud Run, autoscaling,
   managed Redis and a Supabase Large or XL database. The code already supports it; only the
   deploy target changes (`production-deploy.yml`).

## 16. What only you can do, and why

I can't do the account steps for you:
- creating accounts;
- proving you're a student (ID upload);
- accepting each service's terms;
- choosing passwords and two-factor codes.

They need you personally, and they bind you to those services. Everything after that is
scripted:
- the server, its hardening and backups: `provision-azure.sh`;
- settings: `compose_env.py`;
- deploys with rollback: `free-tier-deploy.yml`;
- testing the server setup: `free-tier-stack.yml`;
- backups: `db-backup.yml`;
- uptime: `uptime.yml`.
