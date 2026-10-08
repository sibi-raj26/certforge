"""AI feature: personalised certificate citations via Claude (falls back to templates offline)."""
import os

_TONE = {"Excellence": "exceptional performance, initiative and dedication", "Distinction": "strong performance and a proactive attitude",
         "Merit": "consistent effort and reliable contribution", "Completion": "commitment and willingness to learn"}

def _fallback(c, company):
    return (f"{c['name'].split()[0]} showed {_TONE.get(c['tier'], 'dedication')} as {c['role']}, "
            f"making a valued contribution to {company}'s {c['department']} team.")

def generate_citation(c: dict, company: str) -> tuple[str, str]:
    """Returns (text, source) where source is 'ai' or 'template'."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return _fallback(c, company), "template"
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        prompt = (f"Write a warm, professional 1-2 sentence certificate citation (max 35 words, no quotes) for intern "
                  f"{c['name']}, {c['role']} in {c['department']} at {company}, internship {c.get('start','')} to {c.get('end','')}. "
                  f"Overall performance level: {c['tier']}. Do NOT mention numeric scores, attendance or percentages; do not invent specific projects.")
        r = client.messages.create(model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6"), max_tokens=120,
                                   messages=[{"role": "user", "content": prompt}])
        return r.content[0].text.strip(), "ai"
    except Exception:
        return _fallback(c, company), "template"
