# Idea Forge — Setup Guide

Every morning, a team of AI agents explores **300+ unconventional ways to make money**, using only approaches that need:

- no competitive edge, special skills or network
- no selling
- little capital
- automation instead of constant human work

The engine evaluates every approach and sends you **one PDF on Telegram (around 08:00 Addis Ababa time)** with the single strongest idea of the day, even on days when that idea isn't worth pursuing, plus a few worthy mentions.

It runs in the same GitHub repository as SCARA and uses the same Telegram bot and secrets.

---

## How it works

```
 Today's headlines ─┐
 Random building    │   ① GENERATE ~320 approaches       10 agent personas × 6 thinking methods
 blocks (sandbox) ──┼─► ② FILTER     capital ≤ $500, no high-contact or high-legal-risk ideas
 Past best ideas ───┘   ③ DEDUPE     drop anything seen in the last 45 days
                        ④ SCREEN     cheap batch scoring on 9 criteria → top 12
                        ⑤ PANEL      Skeptic + Lawyer + Engineer + Economist + Judge review each
                        ⑥ REALITY    how many HN stories / GitHub repos already exist (crowdedness)
                        ⑦ FINAL      top 4 compete head-to-head → winner
                        ⑧ REPORT     simple PDF → your Telegram
```

**Why it explores so widely.** Each generation call gets a randomly chosen agent persona (Loophole Lawyer, Data Scavenger, Systems Physicist, Timekeeper, Historian of Dead Gaps…) and a randomly chosen thinking method:

| Method | What the agent is asked to do |
|---|---|
| Combinator | Mash together random systems × gaps × triggers × automation tools |
| Signal | React to today's real headlines: what window just opened? |
| Analogy | Take a famous loophole that has closed and find the same structure somewhere else today |
| Inversion | What are people *forced* to do that leaks value? |
| Evolve | Mutate and combine the best ideas from previous days |
| Wildcard | Deliberately strange, unexpected angles |

**Why the winner is trustworthy-ish.** LLMs are bad at giving consistent 1–10 scores but decent at choosing between two options, so the final pick is decided head-to-head. The panel is told that "No" is a normal verdict, and the PDF's verdict always matches the panel's.

**What's in each PDF:**
1. **The idea**, in 2–3 plain sentences
2. **Worth pursuing?** Yes / Test first / No, with one short reason
3. How it would work, step by step
4. Limitations
5. Technical notes: the cheapest test (≤1 day, ≤$20), when to kill it, capital needed, tools, data sources, free resources, and an automation plan
6. Why it won: scores, the head-to-head record, the crowdedness check, and the skeptic's view
7. Worthy mentions: about 6 runner-ups, one sentence each
8. Stats for the day's run

---

## Setup

### If you already set up SCARA (about 10 minutes)

1. **Upload the new files.** In your `scara-engine` repository, click **Add file → Upload files**. Drag in **everything** from the new zip and click **Commit changes**. Files with the same name are replaced; your saved state is kept.
   - Check that `.github/workflows/forge.yml` now exists. If the hidden folder didn't upload, create the file by hand (**Add file → Create new file**, name it `.github/workflows/forge.yml`, and paste in the file's contents).
2. **Add a free Gemini key (no card needed).** The Forge uses about 100 LLM calls a day. Gemini handles most of them, which leaves your Groq quota for SCARA.
   - Go to **aistudio.google.com**, sign in with your Google account, and click **Get API key → Create API key**.
   - In GitHub, go to **Settings → Secrets and variables → Actions → New repository secret**, with the name `GEMINI_API_KEY` and your key as the value.
   - Your existing `GROQ_API_KEY` is used automatically as the backup. Here it runs Groq's larger model, which has its own daily allowance.
   - Optional third backup: a **Mistral** key from console.mistral.ai (free plan, asks for a phone number but no card), saved as `MISTRAL_API_KEY`.
3. **Test it.** Go to **Actions → Idea Forge (daily) → Run workflow**, choose `check`, and click **Run workflow**. You should get a Telegram message: *"✅ Idea Forge is connected."*
4. **Get your first PDF now.** Run it again with `run`. It takes about an hour, then the PDF arrives on Telegram.

From now on it runs every day by itself.

### If you haven't set up SCARA yet

Follow steps 1–5 in `README.md` first: create the repository, upload the files, get a Groq key, create the Telegram bot, and add the secrets. Then do steps 2–4 above.

---

## Customising (optional)

| What | Where |
|---|---|
| More or fewer ideas per day | `forge_config.yaml` → `generation_calls` (40 calls ≈ 320 ideas) |
| Maximum starting capital | `forge_config.yaml` → `max_start_capital_usd` |
| Number of worthy mentions | `forge_config.yaml` → `worthy_mentions` |
| Delivery time | `.github/workflows/forge.yml` → `cron: "7 4 * * *"` (UTC: 4 = 07:00 Addis) |
| **Widen the sandbox** | `forge/lenses.py`: add your own systems, gaps, triggers, personas or historical loopholes. This is the most powerful setting. |
| Headlines the agents react to | `forge_config.yaml` → `signal_feeds` (any RSS feed) |

## If something goes wrong

| Problem | Fix |
|---|---|
| Telegram says "no usable ideas today" | LLM quotas ran out or a model name changed. Add `MISTRAL_API_KEY` as an extra backup, or update `model:` in `forge_config.yaml`. |
| "No LLM key found" | Add at least one of `GEMINI_API_KEY`, `GROQ_API_KEY`, `MISTRAL_API_KEY`. |
| No PDF and no message at all | Open **Actions → Idea Forge (daily)**, click the failed run, and read the red step. Send it to Claude to fix. |

**Important.** The ideas are AI-generated and **unverified**. The rule built into every report: run the *cheapest test* before risking any money.
