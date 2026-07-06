"""Prompt templates for the AI domain.

Pure string-building functions — no I/O, no model calls. Kept separate from
app/ai/service.py so prompt wording can be iterated on independently of the
orchestration logic (D-03, D-05).

Security note (RESEARCH.md Security Domain, threat T-05-04): note content is
first-party (the caller's own note) but is wrapped in explicit delimiters as
a forward-compatible prompt-injection habit — Phase 6 introduces cross-note
retrieval where this discipline starts to matter for real.
"""

# Bounded max character count fed into a prompt — a DoS guard against an
# unbounded note blowing up prompt size / inference time (T-05-02).
_MAX_PROMPT_CONTENT_CHARS = 8000


def _truncate(content: str) -> str:
    """Truncate content to a bounded max length before prompting (T-05-02)."""
    if len(content) <= _MAX_PROMPT_CONTENT_CHARS:
        return content
    return content[:_MAX_PROMPT_CONTENT_CHARS] + "... [truncated]"


def build_summarize_prompt(content: str) -> str:
    """Build the prompt instructing a 2-3 sentence summary (D-03)."""
    safe_content = _truncate(content)
    return (
        "You are a concise summarization assistant. Summarize the note content "
        "below in exactly 2-3 sentences. Only output the summary text — no "
        "preamble, no bullet points, no quotation marks.\n\n"
        "--- NOTE CONTENT START ---\n"
        f"{safe_content}\n"
        "--- NOTE CONTENT END ---"
    )


def build_tag_prompt(content: str) -> str:
    """Build the prompt instructing a JSON list of short tag strings (D-05).

    Output is untrusted model text — the caller must run it through
    `_parse_tag_list` before use (never eval'd, never trusted as-is).
    """
    safe_content = _truncate(content)
    return (
        "You are a tagging assistant. Suggest 3-5 short, lowercase tags for "
        "the note content below. Respond with ONLY a JSON list of strings, "
        'like ["tag-one", "tag-two"] — no preamble, no explanation, no other '
        "keys or text.\n\n"
        "--- NOTE CONTENT START ---\n"
        f"{safe_content}\n"
        "--- NOTE CONTENT END ---"
    )
