"""
slack_bot.py — Delivery: Slack Bot (Stage 2+)
----------------------------------------------
Uses Slack Bolt SDK (free — Slack licence already paid).
Build time: 2–5 days. Adoption friction: zero.

Setup:
  1. Create a Slack App at https://api.slack.com/apps
  2. Enable Socket Mode
  3. Add Bot Token Scopes: app_mentions:read, chat:write, im:history, im:read, im:write
  4. Set SLACK_BOT_TOKEN, SLACK_SIGNING_SECRET, SLACK_APP_TOKEN in .env

Usage:
  python delivery/slack_bot.py

The bot responds to:
  - DMs: ask anything directly
  - Channel mentions: @YourBotName did the February campaign work?
"""

import os
import logging
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv

from agents.orchestrator import run_pipeline

load_dotenv()
logging.basicConfig(level=logging.INFO)

app = App(
    token=os.getenv("SLACK_BOT_TOKEN"),
    signing_secret=os.getenv("SLACK_SIGNING_SECRET"),
)


def _post_thinking(client, channel: str, thread_ts: str | None) -> str:
    """Post a 'thinking' message while the pipeline runs."""
    msg = client.chat_postMessage(
        channel=channel,
        thread_ts=thread_ts,
        text="⏳ Analysing your question...",
    )
    return msg["ts"]


def _update_thinking(client, channel: str, ts: str, text: str) -> None:
    client.chat_update(channel=channel, ts=ts, text=text)


def handle_query(body, say, client, logger) -> None:
    """Core handler for both DMs and app_mentions."""
    event = body.get("event", {})
    text = event.get("text", "").strip()
    channel = event.get("channel")
    thread_ts = event.get("thread_ts") or event.get("ts")
    user = event.get("user")

    # Strip the bot mention from the text if present
    if "<@" in text:
        text = text.split(">", 1)[-1].strip()

    if not text:
        say(
            text="👋 Hi! Ask me anything about promotional performance, inventory, "
                 "regional sales, or campaign impact. For example: "
                 "_'Did the February campaign improve sales in the South?'_",
            thread_ts=thread_ts,
        )
        return

    # Post thinking indicator
    thinking_ts = _post_thinking(client, channel, thread_ts)
    progress_messages = []

    def on_step(msg: str):
        progress_messages.append(msg)
        _update_thinking(client, channel, thinking_ts, "\n".join(progress_messages))

    # Run the pipeline
    result = run_pipeline(text, on_step=on_step)

    # Replace thinking message with actual answer
    if result.status == "success":
        answer = result.slack_answer
        footer = f"\n\n_Query time: {result.total_latency_ms}ms · Intent: {result.intent.get('intent')}_"
    elif result.status == "clarification_needed":
        answer = result.formatted_answer
        footer = ""
    elif result.status == "blocked":
        answer = result.formatted_answer
        footer = ""
    else:
        answer = f"❌ Something went wrong: {result.error}"
        footer = ""
        logger.error(f"Pipeline error for query '{text}': {result.error}")

    _update_thinking(client, channel, thinking_ts, answer + footer)


@app.event("app_mention")
def handle_mention(body, say, client, logger):
    handle_query(body, say, client, logger)


@app.event("message")
def handle_dm(body, say, client, logger):
    event = body.get("event", {})
    # Only handle DMs (channel_type == "im"), not channel messages without mention
    if event.get("channel_type") == "im" and not event.get("bot_id"):
        handle_query(body, say, client, logger)


if __name__ == "__main__":
    handler = SocketModeHandler(app, os.getenv("SLACK_APP_TOKEN"))
    print("⚡ FMCG Analytics Slack Bot is running!")
    handler.start()
