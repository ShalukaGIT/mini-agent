# mini-agent

A tiny agent that lives in GitHub Actions. No server, no always-on machine, no bills.

It wakes on a schedule (or when you press a button), asks **DeepSeek Flash v4** (via Roar AI)
something useful, and sends the answer to **Telegram**.

## Why this exists

A reminder agent needs to run when your laptop is asleep. A full cloud VM means a card,
a fraud check, and a monthly bill. GitHub Actions gives public repos unlimited free minutes
and needs none of that.

## Jobs

| Task | When (Sri Lanka) | What |
|---|---|---|
| `morning` | 07:00 daily | Short brief: study focus, habit nudge, encouragement |
| `evening` | 19:00 daily | Three review questions for the day |
| `test` | on demand | Prints `MINI_AGENT_OK` to prove the wiring works |

Times live in `.github/workflows/mini-agent.yml` as UTC cron. Sri Lanka is **UTC+5:30**, so
07:00 local = `30 1 * * *` and 19:00 local = `30 13 * * *`.

## Run it manually

Actions -> **mini-agent** -> *Run workflow*:

- leave `message` empty, pick a `task` -> runs that task
- fill `message` -> runs your prompt instead

## Add a new job

1. Open `tasks.json`
2. Add an entry:

```json
{
  "name": "weigh_in",
  "title": "Weekly weigh-in nudge",
  "enabled": true,
  "prompt": "Write one short encouraging sentence about tracking progress weekly."
}
```

3. If you want it on a schedule, add a `cron:` line to the workflow and map it in the
   *Pick task* step (see the existing two for the pattern)
4. Commit. It is live on the next run.

Turn a job off without deleting it: set `"enabled": false`.

## Required secrets

Set in Settings -> Secrets and variables -> Actions:

| Secret | What |
|---|---|
| `ROAR_AI_API_KEY` | Roar AI key |
| `TELEGRAM_BOT_TOKEN` | token from @BotFather |
| `TELEGRAM_CHAT_ID` | your numeric Telegram user id |

## Notes

- **`max_tokens` must stay >= 400.** DeepSeek Flash spends reasoning tokens before it emits
  visible text. At 60-200 tokens the reply gets truncated and corrupted (it emitted Chinese
  characters mid-word in testing). Default is 800.
- Costs are cents per year. Each run is ~100 input / ~200 output tokens.
- `DRY_RUN=1 python agent.py --task test` prints instead of sending.
- Public repo = unlimited Actions minutes. Keep it public, keep it free.
