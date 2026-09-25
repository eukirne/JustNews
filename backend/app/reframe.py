from __future__ import annotations

import logging
from dataclasses import dataclass

from anthropic import AsyncAnthropic

from .articles import StoryCluster
from .config import get_settings

logger = logging.getLogger("brightside.reframe")

CATEGORIES = ["World", "UK/Local", "Politics", "Economy", "Science", "Health", "Culture", "Sports"]

SYSTEM_PROMPT = """You are the editorial engine for Just News, a news site that \
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
   Science, Health, Culture, Sports. Any story about sport — match results, transfers, \
   disciplinary decisions (red cards, bans, appeals), injuries, a manager's or player's \
   press-conference comments or personal reaction to something in their sport — is \
   Sports, full stop, even when it's framed around one person's personal quote, regret, \
   or opinion ("[Manager] says he regrets..."). Never categorize sports content as \
   Culture, UK/Local, or anything else because of how it's framed — this matters because \
   Sports is hidden from the site's default front page and only shown on its own tab, so \
   a miscategorized sports story leaks onto the front page.
9. Set exclude=true for any story centered on one named individual's case or personal \
   situation rather than something that affects or matters to a broad audience — this \
   includes but is not limited to: a routine local crime report, an individual's arrest, \
   charge, bail, sentencing, or other court outcome, an inquest into one person's death, \
   a local road crash, a missing-person case, a birthday/anniversary or "local hero" \
   human-interest piece, an individual profile, or a tribute/obituary about one person \
   (e.g. "a woman in Exeter who..."). These do not get published regardless of how \
   sympathetic, well-written, or heartwarming the source coverage is — this site only \
   publishes stories with general relevance, not one person's story.
   A single case does NOT become general-relevance just because an official, commissioner, \
   watchdog, victim's advocate, or other public figure is quoted criticizing the outcome — \
   "[Official] says the [bail/sentencing/release] decision in [one person's] case was a \
   failure" is still fundamentally a single-case crime/court story, and the critical quote \
   doesn't change that. Exclude it. A story only clears the bar on institutional-failure \
   grounds when the failure itself is the substance and it is genuinely systemic: a formal \
   inquiry, audit, or review's findings, a pattern across many cases backed by data or \
   named specifics (not just an official's assertion that it's a pattern), or a resulting \
   policy or process change — not one official's reaction to one case.
   Do NOT exclude a story just because a named individual appears or is quoted in it, if \
   the substance is genuinely general-interest: a change in national or local policy, an \
   economic report, a scientific discovery, a public-health finding, a court ruling that \
   sets precedent or affects many people, a natural disaster's aid/response effort, a \
   war-crimes investigation, terrorism with a national dimension, a genuinely systemic \
   institutional failure as described above, or major sports results.
   The test is always: does this affect or matter to people generally, or is it really \
   just this one person's case? When genuinely unsure, only include it if it is clearly \
   the former; otherwise exclude it. When exclude=true, still fill in headline/summary/ \
   category as best you can — they will not be published, but the field is required.
10. Rate importance from 1-10: how much this story matters to an internationally-minded, \
   educated reader who wants to understand what actually matters in the world — the kind \
   of reader The Economist and the New York Times' front page are written for, not a local \
   paper's. Judge by consequence and reach, not novelty or human interest:
   - 8-10: major geopolitical developments; national elections, leadership changes, or \
     policy shifts with broad consequences; market- or economy-moving news (central bank \
     decisions, major economic data, systemic financial events); large-scale conflict, \
     disaster, or humanitarian developments; significant scientific or technological \
     breakthroughs; major public health developments affecting large populations.
   - 4-7: meaningful but narrower in scope or consequence — notable national policy or \
     corporate news, regional developments with some broader signal, science/health \
     stories of moderate significance, substantial developments in an ongoing major story.
   - 1-3: real news that cleared the relevance bar in rule 9 but is narrow, incremental, \
     or parochial in scope — a minor update with little new substance, a local policy \
     decision with no broader implications, a niche development.
   A story being in the UK/Local category does not by itself lower this score — judge the \
   actual stakes and reach of the story, not its section. When exclude=true, importance \
   is still required; use your best estimate.

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
            "exclude": {
                "type": "boolean",
                "description": "true if this is a personal/individual-focused story (crime, accident, human-interest, profile, tribute, etc.) rather than something of general relevance — see rule 9.",
            },
            "importance": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10,
                "description": "1-10 editorial importance for an internationally-minded, educated reader — see rule 10.",
            },
        },
        "required": ["headline", "summary", "category", "exclude", "importance"],
    },
}


@dataclass
class ReframedStory:
    headline: str
    summary: str
    category: str
    exclude: bool = False
    importance: int = 5


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
                try:
                    importance = int(data.get("importance", 5))
                except (TypeError, ValueError):
                    importance = 5
                importance = max(1, min(10, importance))
                return ReframedStory(
                    headline=data["headline"].strip(),
                    summary=data["summary"].strip(),
                    category=category,
                    exclude=bool(data.get("exclude", False)),
                    importance=importance,
                )

        raise RuntimeError("Claude response did not include a publish_story tool call")
