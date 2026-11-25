"""The building blocks the generators combine at random — the 'sandbox'.

Every generation call draws a different random mix of these, so the models
are pushed into corners of the idea space they wouldn't visit on their own.
Add your own lines freely: more variety = stranger ideas.
"""

SYSTEMS = [
    "public blockchains and DeFi protocols", "government grant, rebate and incentive programs",
    "class-action and regulatory settlement funds", "unclaimed-property and dormant-account registries",
    "online marketplaces with regional price differences", "price-match and price-protection guarantees",
    "airline, hotel and retail loyalty programs", "cashback and referral-free rebate portals",
    "public procurement and surplus/liquidation auctions", "expiring domains, handles and namespaces",
    "expired patents, trademarks and copyrights entering the public domain", "open government datasets",
    "public APIs with generous free tiers", "app-store and browser-extension ecosystems",
    "prediction markets and forecasting tournaments", "prize competitions and open bounties",
    "bug-bounty and vulnerability-disclosure programs", "currency conversion and cross-border payment fees",
    "tax credits, deductions and treaty rules", "refund, chargeback and warranty policies",
    "carbon-credit and environmental-incentive registries", "energy-market demand-response programs",
    "telecom and data roaming pricing", "event/ticketing primary-sale systems",
    "print-on-demand and digital-goods platforms", "AI model marketplaces and compute spot markets",
    "open-source funding and sponsorship platforms", "testnets, incentivised betas and points programs",
    "SEC/EDGAR filings and corporate actions", "bankruptcy claims and court-ordered distributions",
    "lottery-like systems with positive-expected-value edge cases", "fuel, transit and toll pricing systems",
    "academic and public research data releases", "satellite, weather and sensor open-data feeds",
    "abandoned or deprecated online services", "time-limited platform launch incentives",
]

GAPS = [
    "information latency (some people learn a fact minutes/days before the price reflects it)",
    "fragmentation (the same thing priced differently in different places)",
    "unclaimed value (money owed to anyone who asks, that few ask for)",
    "rules nobody reads (fine print that grants rights or rewards)",
    "threshold effects (a small change crosses a line that triggers a big payout)",
    "rounding, minimums and granularity errors",
    "expiry and renewal cycles (things that lapse and become free to take)",
    "thin liquidity (markets so small no professional bothers)",
    "stale or slow-updating data (a feed or index that lags reality)",
    "misaligned incentives (a system paying for behaviour it didn't intend to reward)",
    "geographic or eligibility restrictions that few eligible people use",
    "launch subsidies (a new system overpays early participants to bootstrap)",
    "boring/tedious work no one automates", "transition windows when rules change",
    "mispriced optionality (a free option bundled into something else)",
    "aggregation gaps (many tiny amounts nobody bothers to collect)",
    "timezone and calendar effects", "status/tier systems that can be reached cheaply",
]

TRIGGERS = [
    "a new law or regulation taking effect", "a platform launching or shutting down a feature",
    "a company going bankrupt or being acquired", "a token or program launch",
    "a data feed being published on a fixed schedule", "a seasonal or calendar event",
    "a price crossing a threshold", "a policy change announced but not yet effective",
    "a popular service raising prices", "a deadline approaching with low participation",
    "a natural or market shock", "a technology becoming suddenly cheap (e.g. AI inference)",
]

AUTOMATIONS = [
    "a scheduled GitHub Actions job", "a free LLM reading documents daily", "a Telegram alert bot",
    "a web-scraper on a free tier", "an on-chain listener", "an RSS/regulatory-feed watcher",
    "a no-code automation (n8n self-hosted / free tier)", "a spreadsheet with scheduled formulas",
    "a browser automation script", "a simulation that runs before any money moves",
]

PERSONAS = [
    ("Loophole Lawyer", "reads fine print, terms and statutes looking for rights and payouts others ignore"),
    ("Data Scavenger", "finds value in free public datasets and feeds that nobody combines"),
    ("Systems Physicist", "models systems as flows and looks for leaks, pressure differences and lag"),
    ("Arbitrage Trader", "looks for the same thing at two prices and the cheapest path between them"),
    ("Automation Hacker", "finds tedious, small-value tasks that become profitable when done 10,000× by a bot"),
    ("Contrarian", "starts from what everyone assumes is worthless and asks why it might not be"),
    ("Historian of Dead Gaps", "knows past loopholes that closed and hunts for the same structure elsewhere today"),
    ("Incentive Designer", "spots systems that pay for behaviour they didn't intend to reward"),
    ("Timekeeper", "focuses only on timing: windows, deadlines, schedules, lags and first-mover moments"),
    ("Global Nomad", "exploits differences between countries, currencies, time zones and eligibility rules"),
]

HISTORICAL_GAPS = [
    "matched betting (risk-free sportsbook sign-up offers, now restricted)",
    "credit-card sign-up bonus churning", "domain drop-catching of expiring names",
    "coin-roll hunting for valuable old coins", "US Mint dollar-coin programme cashback loop",
    "early DeFi liquidity-mining yields", "free airdrops for early testnet users",
    "penny-stock odd-lot tender offers", "SPAC trust-value arbitrage", "retail arbitrage of clearance items",
    "Amazon price-drop refunds", "early YouTube/AdSense long-tail niches",
    "unclaimed class-action settlements", "bottle-deposit arbitrage across state lines",
    "ICO/exchange listing timing gaps", "free-to-play game item arbitrage",
    "expired-patent product clones", "early cloud-credit startup programs",
]

OPERATORS = {
    "combinator": "Combine the random building blocks below into genuinely new approaches.",
    "signal": "React to TODAY's real headlines below: what new gap or window do they open right now?",
    "analogy": "Take the historical gap below (now closed) and find where the SAME underlying structure "
               "exists today, unnoticed, in a different system.",
    "inversion": "Invert: what are people or systems FORCED to do that leaks value, and how could someone "
                 "stand downstream of that leak?",
    "evolve": "Here are strong ideas from previous days. Mutate, combine or push them further into "
              "new, stronger variants (don't repeat them).",
    "wildcard": "Go maximally unconventional. Ignore what sounds normal. Odd, surprising, specific approaches only.",
}
