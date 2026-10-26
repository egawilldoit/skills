# Video Knowledge — audit checklist

## Source fidelity
- [ ] Every distinct idea, example, number, tool, exception and contradiction is covered.
- [ ] Same phrase used for different purposes is not conflated.
- [ ] Report uncertainty, source omissions and partial transcription.
- [ ] Do not invent title, creator, visual events, duration, timestamp or a speaker quote.
- [ ] Mark hypothetical numbers and personal heuristics as such.
- [ ] Do not reproduce complete transcripts in output.

## Explanation
- [ ] A relationship-bearing **diagram precedes prose**.
- [ ] Each idea has what/why/example/condition, not just a headline.
- [ ] "Pay attention" surfaces details a casual summary would miss.
- [ ] Distinguish direct source claims from our synthesis and externally verified facts.
- [ ] Practical applications include one realistic reason *not* to apply the technique.
- [ ] Cross-video connections link only known material.
- [ ] The result is understandable without the surrounding chat.

## Third-pass ledger receipt
- **Pass 1**: list source ideas and important concrete cases.
- **Pass 2**: check draft against them; restore omitted material.
- **Pass 3**: challenge evidence quality, attribution, diagram and overstatement.
- Report **covered, corrected, unresolved, excluded**. Avoid unsupported numerical completeness scores.
- Another review with no material improvement ends with "no further supported findings", not invented novelty.

## Anthropic-style skill eval cases
When this skill lives in the EGA catalog, `../../tests/video-knowledge-evals.json` provides **three evaluation specifications**, not execution evidence. Real behavior testing compares responses to the same prompts **with and without** the skill and scores actual outputs. Use sequential execution when subagents are not authorized.
