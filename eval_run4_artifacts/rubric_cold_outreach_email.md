# Cold Outreach Email — Rubric

**Task:** Write a cold outreach email to a Series A founder pitching angel investment
**Domain:** cold_outreach_email
**Total Points:** 56
**Pass Threshold:** 80%

---

## email_subject

**Category:** engagement

**Description:** Subject line is compelling and specific — not generic or spammy

**Pass Condition:** Subject is <60 chars, references something specific to the recipient, creates curiosity without clickbait. No 'Quick question' or 'Touching base'.

**Scoring Method:** WEIGHTED_COMPONENTS (max 10 pts)

| Sub-attribute | Description | Weight | Measurement |
|---|---|---|---|
| specificity | References recipient's company/round/domain | 0.40 | 1.0 if names company or specific context, 0.0 if generic |
| brevity | Under 60 chars, scannable on mobile | 0.25 | 1.0 if ≤60 chars, 0.5 if ≤80, 0.0 if >80 |
| curiosity_hook | Creates reason to open without being clickbait | 0.35 | 1.0 if compelling + honest, 0.5 if generic, 0.0 if spammy |

**Pass Examples:** "$2M angel check for Acme's Series A — operator background in logistics"

**Fail Examples:** "Quick question", "Exciting investment opportunity!"

---

## email_opening

**Category:** engagement

**Description:** First sentence earns the right to the second — no throat-clearing

**Pass Condition:** Opens with specific signal: why now, why them, what you noticed. No 'I hope this finds you well' or self-introductions.

**Scoring Method:** PENALTY_BASED (max 8 pts)

| Penalty | Points Deducted |
|---|---|
| generic_greeting | -3.0 |
| self_intro_first | -2.0 |
| no_specific_signal | -2.0 |
| too_long_opening | -1.5 |

**Pass Examples:** "Saw your Techcrunch piece on [X] — the way you're attacking [problem] maps to what I built at [company]"

**Fail Examples:** "Hi, my name is Tim and I'm an angel investor..."

---

## email_value_prop

**Category:** persuasion

**Description:** Clearly articulates what the angel brings beyond capital

**Pass Condition:** Specific operational value: domain expertise, network, customer intros, hiring help. Concrete, not vague ('I can help').

**Scoring Method:** WEIGHTED_COMPONENTS (max 10 pts)

| Sub-attribute | Description | Weight | Measurement |
|---|---|---|---|
| specificity | Names concrete value (intros, expertise, past wins) | 0.45 | 1.0 if 2+ specific offerings, 0.5 if 1 vague, 0.0 if just capital |
| relevance | Value prop maps to recipient's actual needs/stage | 0.35 | 1.0 if clearly relevant to their domain/stage, 0.0 if generic |
| credibility | Claims are verifiable (named companies, outcomes) | 0.20 | 1.0 if verifiable claims, 0.5 if plausible, 0.0 if unsubstantiated |

**Pass Examples:** "I scaled logistics ops from $5M to $80M ARR at ShipCo — happy to open my network of 20+ VP Supply Chain contacts"

**Fail Examples:** "I bring smart capital and strategic value to my portfolio companies"

---

## email_social_proof

**Category:** credibility

**Description:** Establishes credibility without bragging

**Pass Condition:** 1-2 relevant proof points: portfolio wins, operating background, mutual connections. Woven in, not a resume dump.

**Scoring Method:** WEIGHTED_COMPONENTS (max 8 pts)

| Sub-attribute | Description | Weight | Measurement |
|---|---|---|---|
| proof_quality | Proof points are relevant and impressive | 0.50 | 1.0 if directly relevant wins, 0.5 if tangential, 0.0 if absent |
| restraint | 1-2 points, not a resume dump | 0.30 | 1.0 if 1-2 tight proof points, 0.5 if 3-4, 0.0 if resume paragraph |
| natural_integration | Proof woven into narrative, not listed | 0.20 | 1.0 if organic, 0.0 if bullet-pointed credentials |

**Pass Examples:** "...when I was CTO at [X] (acq. by Google), we solved a similar cold-start problem"

**Fail Examples:** "I have 15 years of experience, 30 investments, board seats at..."

---

## email_cta

**Category:** conversion

**Description:** Call to action is low-friction and specific

**Pass Condition:** Single, clear ask. Low commitment (15-min call, not 'let's meet'). Suggests specific times or next step.

**Scoring Method:** WEIGHTED_COMPONENTS (max 8 pts)

| Sub-attribute | Description | Weight | Measurement |
|---|---|---|---|
| clarity | Single unambiguous ask | 0.35 | 1.0 if one clear ask, 0.5 if implied, 0.0 if multiple/confusing |
| low_friction | Minimal commitment required | 0.35 | 1.0 if 15-min call or async, 0.5 if meeting, 0.0 if big ask |
| specificity | Includes proposed time or concrete next step | 0.30 | 1.0 if specific availability, 0.5 if 'sometime this week', 0.0 if open-ended |

**Pass Examples:** "Free for a 15-min call Thursday or Friday afternoon? Happy to share my thesis on [space] first over email if you prefer."

**Fail Examples:** "Let me know if you're interested in chatting sometime."

---

## email_tone

**Category:** voice

**Description:** Tone is peer-to-peer, confident but not presumptuous

**Pass Condition:** Reads like one founder talking to another. Not sycophantic, not salesy, not formal. Respects their time.

**Scoring Method:** PENALTY_BASED (max 6 pts)

| Penalty | Points Deducted |
|---|---|
| sycophantic_language | -2.0 |
| salesy_pressure | -2.0 |
| overly_formal | -1.5 |
| presumptuous_familiarity | -1.5 |
| humble_brag | -1.0 |

**Pass Examples:** Direct, warm, brief — reads like a text from a smart friend

**Fail Examples:** "I'd be truly honored to be part of your incredible journey"

---

## email_length

**Category:** structure

**Description:** Email is scannable in <30 seconds — under 150 words

**Pass Condition:** Under 150 words. Short paragraphs (1-3 sentences). White space between blocks. No walls of text.

**Scoring Method:** WEIGHTED_COMPONENTS (max 6 pts)

| Sub-attribute | Description | Weight | Measurement |
|---|---|---|---|
| word_count | Under 150 words total | 0.50 | 1.0 if ≤150, 0.7 if ≤200, 0.3 if ≤250, 0.0 if >250 |
| scannability | Short paragraphs, visual breaks | 0.50 | 1.0 if all paragraphs ≤3 sentences with breaks, 0.0 if wall of text |

**Pass Examples:** 5 short paragraphs, 120 words total

**Fail Examples:** 3 dense paragraphs, 300+ words
