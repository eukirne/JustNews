from __future__ import annotations

import logging
from dataclasses import dataclass

from anthropic import AsyncAnthropic

from .articles import StoryCluster
from .config import get_settings

logger = logging.getLogger("brightside.reframe")

CATEGORIES = ["World", "UK/Local", "Politics", "Economy", "Science", "Health", "Culture"]

SYSTEM_PROMPT = """You are the editorial engine for The Bright Side, a news site that \
reports real news honestly while filtering out political bias and doom-mongering / \
clickbait framing. You reframe wire-style news summaries around what is genuinely \
true and constructive in them, without ever inventing facts, downplaying real harm, \
or omitting anything essential. Serious stories stay serious. The goal is honest \
framing, never sugar-coating.

You will be given one or more outlets' RSS title + summary for the same news event. \
Follow these rules exactly:

1. Write the summary in your own words. Never quote more than about 15 consecutive \
   words verbatim from the source material (copyright reasons).
2. Identify and lead with the genuine constructive angle when one exists in the \
   source material: what is actually being done about a problem, what recovered or \
   improved, what real accountability or progress happened. Never invent a positive \
   angle that is not present in the source reporting.
3. Never omit facts that would change how seriously a reader should take the story. \
   If people died, say how many, plainly. If a problem is ongoing and unresolved, say so.
4. For ongoing disasters, conflicts, or tragedies: report real casualty/impact figures \
   plainly and first. The "constructive" angle here is the response, aid, accountability, \
   or prevention effort — never the tragedy itself, and never framed to minimize it.
5. Strip loaded partisan language and "us vs. them" framing. Present policy stories \
   neutrally, focused on the actual substance (what the policy does, who it affects, \
   what is verifiably true about its effects) rather than the political conflict around it.
6. If a story genuinely has no constructive angle, do not force one. Present it \
   factually and neutrally instead. A forced or misleading positive spin is a failure.
7. The headline must be a one-line, factual, non-clickbait headline: no ALL CAPS, no \
   manufactured urgency, no vague teasers ("You won't believe...").
8. Categorize the story into exactly one of: World, UK/Local, Politics, Economy, \
   Science, Health, Culture.

Call the publish_story tool with your result. Do not include any other commentary."""

PUBLISH_STORY_TOOL = {
    "name": "publish_story",
    "description": "Publish the reframed version of a news story.",
    "input_schema": {
        "type": "object",
        "properties": {
            "headline": {
                "type": "string",
                "description": "One-line factual headline, no clickbait, no ALL CAPS.",
            },
            "summary": {
                "type": "string",
                "description": "2-4 sentence summary in your own words, following all editorial rules.",
            },
            "category": {
                "type": "string",
                "enum": CATEGORIES,
            },
        },
        "required": ["headline", "summary", "category"],
    },
}


@dataclass
class ReframedStory:
    headline: str
    summary: str
    category: str


def build_user_message(cluster: StoryCluster) -> str:
    lines = ["Source material for one news event, from the following outlet(s):\n"]
    for article in [cluster.primary, *cluster.members]:
        lines.append(f"--- {article.outlet} ---")
        lines.append(f"Title: {article.title}")
        if article.feed_summary:
            lines.append(f"Summary: {article.feed_summary}")
        lines.append("")
    lines.append(
        f"Suggested category based on feed section (verify/override if the content "
        f"clearly belongs elsewhere): {cluster.primary.category_hint}"
    )
    return "\n".join(lines)


class Reframer:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        settings = get_settings()
        self.model = model or settings.claude_model
        self.client = AsyncAnthropic(api_key=api_key or settings.anthropic_api_key)

    async def reframe(self, cluster: StoryCluster) -> ReframedStory:
        message = await self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=[PUBLISH_STORY_TOOL],
            tool_choice={"type": "tool", "name": "publish_story"},
            messages=[{"role": "user", "content": build_user_message(cluster)}],
        )

        for block in message.content:
            if block.type == "tool_use" and block.name == "publish_story":
                data = block.input
                category = data.get("category", "World")
                if category not in CATEGORIES:
                    category = "World"
                return ReframedStory(
                    headline=data["headline"].strip(),
                    summary=data["summary"].strip(),
                    category=category,
                )

        raise RuntimeError("Claude response did not include a publish_story tool call")
