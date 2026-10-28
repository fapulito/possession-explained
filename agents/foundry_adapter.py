"""
agents/foundry_adapter.py — Microsoft Foundry model stub for possession-explained.

This module provides a drop-in replacement for the deterministic `answer()`
function from agents/analyst.py.  In the hackathon demo it is NOT imported or
required; the deterministic analyst runs standalone.

How to activate a Foundry model
────────────────────────────────
1. Replace the body of `answer()` below with an actual Azure AI Foundry /
   Azure OpenAI chat-completion call using the SDK:

       from azure.ai.inference import ChatCompletionsClient
       from azure.core.credentials import AzureKeyCredential

   2. Build a system prompt that instructs the model:
      - It may ONLY cite numbers present in the JSON blob passed in `context`.
      - Every factual sentence must carry a possession_id in [brackets].
      - It must end every answer with the method line.
      - If the question cannot be answered from the data, it must say so.

   3. Pass `context` (the serialised metrics dict) in the system message and
      `question` as the human turn.

   4. Return the model's text response verbatim (do not post-process numbers).

Interface contract (must be preserved)
───────────────────────────────────────
  answer(question: str, context: dict | None = None) -> str

  `question`  — natural-language question string
  `context`   — pre-loaded metrics dict (defaults to the file on disk)
                passed here so callers control what data the model sees
  returns     — answer string; citations and method line guaranteed by prompt

This file must NOT be imported by analyst.py, narrative.py, or recap.py.
"""

from __future__ import annotations

from agents.loader import METRICS


def answer(question: str, context: dict | None = None) -> str:
    """
    Stub: returns the same text a real Foundry call would if the model followed
    the system prompt exactly.  Replace the body with an SDK call to activate.

    A real implementation would look like:

        client = ChatCompletionsClient(
            endpoint=os.environ["AZURE_FOUNDRY_ENDPOINT"],
            credential=AzureKeyCredential(os.environ["AZURE_FOUNDRY_KEY"]),
        )
        response = client.complete(
            model=os.environ.get("FOUNDRY_MODEL", "gpt-4o"),
            messages=[
                {"role": "system", "content": _build_system_prompt(ctx)},
                {"role": "user", "content": question},
            ],
        )
        return response.choices[0].message.content

    ── SLOT FOR FOUNDRY CALL ABOVE ──
    """
    ctx = context if context is not None else METRICS
    # Deterministic fallback so the module is importable and testable without
    # any cloud credentials.  Swap this import for the SDK call above.
    from agents.analyst import answer as deterministic_answer
    return deterministic_answer(question)


def _build_system_prompt(context: dict) -> str:
    """
    Build the system prompt that enforces citation and method-line rules.
    Called by a real Foundry implementation (not the stub).
    """
    import json
    ctx_json = json.dumps(context, indent=2)
    return (
        "You are a sports-analytics assistant.  You may ONLY use numbers present "
        "in the JSON data block below.\n"
        "Rules:\n"
        "  1. Every factual sentence that contains a number must include the "
        "     relevant possession_id(s) in square brackets, e.g. [P0197].\n"
        "  2. Never estimate, round differently from the source, or invent events.\n"
        "  3. If the question cannot be answered from the data, say so explicitly.\n"
        "  4. End every answer with exactly this line:\n"
        "     'Possession % = share of possession-seconds, not event counts.'\n\n"
        f"DATA:\n{ctx_json}"
    )
