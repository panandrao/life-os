"""Prompt construction. Cache-aware ordering:

    system (cached)  →  materials + shared instructions (cached)  →  persona-specific text

Everything before the persona-specific text is byte-identical across all
personas in a run, so it is written to the prompt cache once and read at
0.1x price by every other call (and cache reads don't count against
input-token rate limits).
"""

from __future__ import annotations

from typing import Any

from .models import Persona

SYSTEM_TEXT = """You are a persona agent inside a research simulation. You will be given a
persona card describing a specific fictional person, and one or more materials
that person has been asked to review.

Rules of the simulation:
- Fully inhabit the persona: their background, role, values, priorities, and
  manner of speaking. Answer as they would, not as a helpful AI assistant.
- Ground every reaction in the persona's own experience and stakes. A person's
  role shapes what they notice first and what they ignore.
- Real people disagree, misread things, have pet issues, and bring baggage.
  Do not sand off the persona's edges to be agreeable or balanced.
- In group settings, do not converge toward the group view out of politeness.
  Change your position only if an argument would genuinely move this person,
  and say what moved you when it happens.
- Stay in character at all times. Never mention being an AI, a language model,
  or a simulation."""

GROUP_TURN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "message": {
            "type": "string",
            "description": "What you say to the group, in your persona's voice (a few sentences to a short paragraph).",
        },
        "agreements": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Specific points from named colleagues you agree with, e.g. 'Agree with Dana that X'. Empty if none.",
        },
        "disagreements": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Specific points from named colleagues you disagree with and why. Be candid; empty only if you truly have no disagreement.",
        },
        "position_shift": {
            "type": "string",
            "enum": ["none", "softened", "hardened", "changed"],
            "description": "How this discussion so far has moved your original position.",
        },
    },
    "required": ["message", "agreements", "disagreements", "position_shift"],
    "additionalProperties": False,
}


def response_tool(schema: dict[str, Any], description: str) -> dict[str, Any]:
    return {"name": "submit_response", "description": description, "input_schema": schema}


def shared_prefix_blocks(material_blocks: list[dict[str, Any]], instructions: str) -> list[dict[str, Any]]:
    """Material blocks + shared task instructions, with a cache breakpoint on the last block."""
    blocks = list(material_blocks)
    blocks.append(
        {
            "type": "text",
            "text": f"SHARED TASK INSTRUCTIONS (same for every participant):\n\n{instructions.strip()}",
            "cache_control": {"type": "ephemeral"},
        }
    )
    return blocks


def individual_task_text(persona: Persona) -> str:
    return (
        f"{persona.card()}\n\n---\n"
        "You have just finished reviewing the materials above. Respond to the shared "
        "task instructions as this persona, using the submit_response tool. React from "
        "this persona's specific vantage point — what they would actually notice, "
        "value, worry about, and say."
    )


def group_turn_text(
    persona: Persona,
    group_name: str,
    roster: list[str],
    group_instructions: str,
    moderator_prompt: str | None,
    transcript: list[dict[str, Any]],
    own_initial: str,
    round_no: int,
    total_rounds: int,
) -> str:
    parts = [persona.card(), "\n---\n"]
    parts.append(
        f"You are now in a small-group discussion ({group_name}) with: {', '.join(roster)}.\n"
        f"Discussion task: {group_instructions.strip()}"
    )
    if moderator_prompt:
        parts.append(f"\nMODERATOR: {moderator_prompt.strip()}")
    parts.append(f"\nYour own initial (private) reaction was:\n{own_initial}")
    if transcript:
        lines = [f"[{t['round']}] {t['speaker']}: {t['message']}" for t in transcript]
        parts.append("\nDiscussion so far:\n" + "\n".join(lines))
    else:
        parts.append("\nYou are the first to speak.")
    parts.append(
        f"\nThis is round {round_no} of {total_rounds}. Take your turn using the "
        "submit_response tool. Speak in your persona's voice; engage specifically with "
        "what named colleagues have said; hold your position unless genuinely moved."
    )
    return "\n".join(parts)


def resurvey_text(persona: Persona, transcript: list[dict[str, Any]], own_initial: str) -> str:
    lines = [f"[{t['round']}] {t['speaker']}: {t['message']}" for t in transcript]
    return (
        f"{persona.card()}\n\n---\n"
        f"Earlier, your private reaction to the materials was:\n{own_initial}\n\n"
        "You then took part in this group discussion:\n" + "\n".join(lines) + "\n\n"
        "Now answer the original shared task instructions again, as this persona, "
        "using the submit_response tool. Your answers may have changed, partly "
        "changed, or not changed at all — reflect only genuine movement."
    )


def group_summary_text(group_name: str, transcript: list[dict[str, Any]]) -> str:
    lines = [f"[{t['round']}] {t['speaker']}: {t['message']}" for t in transcript]
    return (
        f"Below is the transcript of small-group discussion {group_name}.\n\n"
        + "\n".join(lines)
        + "\n\nSummarize this discussion for a researcher: main themes, points of "
        "agreement, points of explicit disagreement (preserve dissent — do not "
        "smooth it into consensus), and any positions that shifted and why. "
        "Quote or closely paraphrase participants where useful."
    )
