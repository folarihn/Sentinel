# Sentinel on a VPS with Telegram

This guide is for a Hermes agent running on a server that you talk to through
Telegram (or another Hermes chat platform). It takes about five minutes.

## 1. Install on the server

Connect to the server as the user that runs your Hermes bot:

```shell
ssh youruser@your-server
```

Install and enable Sentinel:

```shell
hermes plugins install https://github.com/folarihn/Sentinel.git --enable
```

Restart the bot so it loads Sentinel. Use `hermes gateway restart`, or restart
your Hermes system service if you run it that way.

## 2. Check it

```shell
hermes sentinel doctor
```

Every line should start with ✓. Each ✗ line says what to fix. If your bot runs
with a custom `HERMES_HOME`, run the command with the same setting.

## 3. Use it from Telegram

Send these to your bot:

| Command | What it shows |
| --- | --- |
| `/sentinel status` | Protection summary, last block, alert setting |
| `/sentinel blocks` | Recent blocked or approval-required actions (`/sentinel blocks 10` for more) |
| `/sentinel missions` | Your mission limits and whether each is active |
| `/sentinel digest` | Plain summary of the last 24 hours (`/sentinel digest 6` for six) |
| `/sentinel alerts on telegram` | Message you when a high-risk action is blocked |
| `/sentinel alerts off` | Stop those messages |

Alerts go to the Telegram **home channel** Hermes uses for scheduled jobs. Set
one with `hermes config set TELEGRAM_HOME_CHANNEL <chat id>` if you have not
already, or name a chat directly: `/sentinel alerts on telegram:<chat id>`.

Chat commands can only read Sentinel's state or switch alerts on and off. They
cannot change policy, missions or files. Anyone who can talk to your bot can use
them, so keep your bot's allowed-user list tight.

To try it, ask the bot to do something risky, such as *"delete the folder named
test"* or *"show me my .env file"*. Sentinel blocks it before it runs.

## What your agent gets

Sentinel also gives the agent three tools. With `sentinel_preflight` it can ask
whether an action would be allowed before trying it, `sentinel_scope` shows its
mission limits, and `sentinel_checkpoint` backs a file up before a risky edit.
None of them can loosen a rule.

If the agent keeps retrying a blocked action (three times in five minutes) or
fires more than 40 tool calls in a minute, Sentinel pauses that session for ten
minutes and alerts you if alerts are on. To let it continue sooner, run
`hermes sentinel resume` on the server.

## 4. Open the dashboard (optional)

On the server:

```shell
hermes sentinel dashboard --workspace /path/the/bot/works/in
```

It prints a **login link**. The dashboard only listens inside the server, so on
**your own computer** open a tunnel first, using the port from the printed link:

```shell
ssh -L 8765:127.0.0.1:8765 youruser@your-server
```

Then open the login link in your browser. The token in the link is moved into
that browser tab and removed from the address bar straight away. Keep the link
private, and press Ctrl+C on the server to stop the dashboard.

Do not open the dashboard port in your firewall or put it behind a public web
address. The SSH tunnel is the supported way in.

## Good to know

- Closing the dashboard does not turn protection off. Sentinel keeps working as
  long as it is enabled in Hermes.
- Sentinel is trusted code inside Hermes, not an operating-system sandbox. Read
  the [security model](SECURITY.md).
- Alerts are rate limited (one per rule per minute, 20 per hour), never include
  the blocked command's arguments, and never change what is allowed. Each
  delivery attempt is recorded in the journal as `alert.sent` or `alert.failed`.
