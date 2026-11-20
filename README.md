# SCARA Opportunity Engine — Setup Guide

This engine searches seven "hunting grounds" for hidden, claimable value four times a day, completely free, and sends PDF reports to your phone.

- **Daily report** every evening at 18:43 (Addis Ababa time)
- **Weekly report** every Monday at 08:11
- **Instant alert** on Telegram whenever a new finding scores very high

You don't need to keep a computer on. It all runs on GitHub's free servers.

Setup takes about 20–30 minutes, once.

---

## Which combination to use

| | **Combo A — Recommended** | Combo B — Extra private | Combo C — Power (later) |
|---|---|---|---|
| Runs on | GitHub Actions, **public** repo | GitHub Actions, **private** repo | A + Oracle Always-Free server + Kaggle GPU |
| Free running time | Unlimited | 2,000 min/month (≈ 2 short scans a day) | Unlimited, 24/7 |
| LLMs | Groq (+ Cerebras backup) | same | + a local model on Kaggle |
| Reports | Telegram | Telegram | Telegram |
| Is your data private? | Yes. Findings are encrypted and only ever sent to *your* Telegram. Only the code is public. | Yes, and the code is hidden too | Yes |
| Setup effort | Easiest | Easy, plus one setting change | Advanced (not covered here) |

**Start with Combo A.** The code being public doesn't matter: it's generic scanning code. Everything it *finds* is encrypted or delivered privately.

If you prefer Combo B, follow the same steps but make the repository private, then open `config.yaml` and change `scan_budget_minutes: 40` to `scan_budget_minutes: 12`.

---

## Step 1 — Create a GitHub account and an empty repository (5 min)

1. Go to **github.com** and sign up (free). Skip this if you already have an account.
2. Click the **+** at the top right, then **New repository**.
3. Name it `scara-engine`, choose **Public**, and click **Create repository**.

## Step 2 — Upload the files (5 min)

1. Unzip `scara-engine.zip` on your computer.
2. On your new repository page, click **uploading an existing file** (or **Add file → Upload files**).
3. Open the unzipped folder, select **everything inside it**, and drag it into the browser window. Click **Commit changes**.

> ⚠️ **The hidden `.github` folder.** Computers often hide folders that start with a dot. If, after uploading, your repository has no `.github` folder:
> - Click **Add file → Create new file**.
> - In the name box, type exactly `.github/workflows/scara.yml`. The slashes create the folders automatically.
> - Open `scara.yml` from the zip (inside `.github/workflows/`) in a text editor, copy everything, paste it in, and click **Commit changes**.
>
> (Mac tip: press **Cmd + Shift + .** in Finder to show hidden folders.)

## Step 3 — Get a free LLM key (3 min)

You need **at least one**. Groq is the best first choice: it's fast, and its free tier doesn't train on your data.

1. Go to **console.groq.com** and sign in with Google or email.
2. Click **API Keys → Create API Key**, name it `scara`, and **copy the key** (it starts with `gsk_`).

Optional backups (the engine switches to these automatically if Groq's daily limit runs out):

- **Cerebras:** cloud.cerebras.ai → API Keys
- **Google Gemini:** aistudio.google.com → Get API key
- **OpenRouter:** openrouter.ai → Keys

## Step 4 — Create your Telegram bot for the PDF reports (5 min)

1. In Telegram, search for **@BotFather** and open it.
2. Send `/newbot`, choose a name (e.g. *My SCARA*) and a username ending in `bot` (e.g. `myscara_reports_bot`).
3. BotFather replies with a **token** like `7123456789:AAH...`. Copy it.
4. Search for your new bot by its username, open it, and press **Start**. *This step matters: a bot can't message you until you've started it.*
5. Search for **@userinfobot**, press **Start**. It replies with your **Id** (a number like `412345678`). Copy it. That's your chat ID.

<details>
<summary>Prefer email instead? (Gmail)</summary>

1. Your Google account needs 2-Step Verification turned on.
2. Go to **myaccount.google.com/apppasswords**, create an app password named `scara`, and copy the 16-letter code.
3. In Step 5, add these secrets instead of (or as well as) the Telegram ones: `EMAIL_USER` = your Gmail address, `EMAIL_APP_PASSWORD` = the 16-letter code, and optionally `EMAIL_TO` = where to send reports.
</details>

## Step 5 — Add your secrets to GitHub (5 min)

In your repository, go to **Settings → Secrets and variables → Actions → New repository secret**. Add each of these, one at a time:

| Name (type exactly) | Value | Required? |
|---|---|---|
| `GROQ_API_KEY` | your Groq key | ✅ (or another LLM key) |
| `TELEGRAM_BOT_TOKEN` | the token from BotFather | ✅ (or email) |
| `TELEGRAM_CHAT_ID` | your number from @userinfobot | ✅ (or email) |
| `STATE_PASSPHRASE` | a long password you make up, e.g. `green-river-coffee-7741-lamp` | ✅ |
| `CEREBRAS_API_KEY` | Cerebras key | optional |
| `GEMINI_API_KEY` | Gemini key | optional |
| `OPENROUTER_API_KEY` | OpenRouter key | optional |

> **Write down your `STATE_PASSPHRASE`.** It encrypts the engine's memory (everything it has seen and found). If you lose it, the engine starts fresh. Nothing breaks, but the history is gone.

## Step 6 — Switch it on and test (3 min)

1. Open the **Actions** tab of your repository. If asked, click **"I understand my workflows, go ahead and enable them."**
2. Click **SCARA Opportunity Engine** on the left, then **Run workflow**, choose `check`, and click the green **Run workflow** button.
3. Within about a minute you should get a Telegram message: **"✅ SCARA is connected."**
4. Run it again with `scan`. The first scan takes about 40 minutes.
5. When the scan finishes, run it once more with `daily`. Your first PDF arrives on Telegram.

**That's it. From now on it runs by itself:**

| What | When (Addis Ababa time) |
|---|---|
| Scan of all 7 grounds | 03:17 · 09:17 · 15:17 · 21:17 |
| Daily PDF report | 18:43 every day |
| Weekly PDF report | Monday 08:11 |
| Instant alert | whenever a new finding scores ≥ 50 |

GitHub sometimes starts scheduled jobs 5–30 minutes late. That's normal.

---

## Optional: let ground #3 check your own wallets

1. Open `config.yaml` in your repository and click the ✏️ pencil icon.
2. Under `my_wallets:` add your **public** wallet addresses, like this:
   ```yaml
   my_wallets:
     - "0x1234...abcd"
   ```
3. Click **Commit changes**.

**Never put a private key or seed phrase anywhere in this repository.**

---

## What the seven grounds do

| # | Ground | What it looks for | What it's allowed to do |
|---|---|---|---|
| 1 | Unclaimed incentive functions | Contracts on less-watched chains that pay *anyone* who calls an upkeep function. Each is checked with a free simulation. | Report (auto-claim comes later) |
| 2 | Assets below redeemable value | DAO treasuries worth more than the token's market cap; US tender offers with odd-lot priority | Report |
| 3 | Rewards you already qualify for | Unclaimed rewards on *your* wallets (Merkl) | Report |
| 4 | New incentive programs | Fresh DAO governance proposals that create claimable rewards | Report |
| 5 | Computational prizes | Changes on prize/bounty pages | Report |
| 6 | Rule changes | Regulator and ecosystem announcements that open a new window | Report |
| 7 | Long-tail bugs | Risky code in newly verified contracts, with a draft disclosure. Marked **PRIVATE**. | **Never acts.** Disclose to the project only. |

This first version is **search-and-report only**. It holds no wallet and can't spend anything. Once a couple of weeks of reports show which grounds produce real hits, an execution module (hot wallet, hard caps, kill switches, run from an always-on server rather than GitHub) can be added for grounds 1–4.

The engine also shares its time automatically. Grounds that produce hits get more of each scan's 40 minutes; quiet ones get less, but never zero.

---

## If something doesn't work

| Problem | Fix |
|---|---|
| No Telegram message after `check` | Did you press **Start** on your bot? Are the secret names spelled exactly as above? |
| "STATE_PASSPHRASE does not match" | You changed the passphrase. Put the old one back, or delete `state/state.db.enc` to start fresh. |
| A ground shows "unavailable" errors in the report | A free website was down or rate-limited. It retries next scan. Nothing to do. |
| LLM errors on every run | A model name was retired. Open `config.yaml` and update `model:` for that provider (its website lists current models). |
| Scheduled runs stopped | GitHub pauses schedules after 60 days with no repository activity. The engine's automatic state commits normally prevent this; if it happens, open **Actions** and click **Enable workflow**. |

**Privacy note:** the GitHub Actions logs are visible to anyone in a public repo, so the engine only ever prints *counts* there ("ground #1: 12 items, 0 hits"). It never prints findings.
