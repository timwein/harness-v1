# Rubric: attention_explanation

**Domain:** explanation
**Total Points:** 34
**Pass Threshold:** 0.8

## Criterion 1: expl_accuracy
**Category:** correctness
**Max Points:** N/A
**Description:** Technical content is correct — no simplification-induced errors
**Pass Condition:** Query/Key/Value framework explained correctly with specific mention that queries attend to keys, not values directly. Dot product similarity calculation explicitly described (not just mentioned). Softmax normalization purpose explained (probabilities sum to 1). Multi-head attention's parallel processing advantage specifically articulated. No conceptual errors about information flow.

## Criterion 2: expl_accessibility
**Category:** audience_fit
**Max Points:** N/A
**Description:** Uses language and concepts accessible to a smart 16-year-old with basic algebra knowledge
**Pass Condition:** All technical terms (attention, query, key, value, softmax, multi-head) defined in plain English when introduced. Analogies are extended metaphors (not just brief comparisons) using familiar domains. Mathematical operations described with concrete examples or visual language. Zero ML/AI jargon without explanation.

## Criterion 3: expl_engagement
**Category:** communication
**Max Points:** N/A
**Description:** Writing style maintains reader interest through accessible, enthusiastic tone
**Pass Condition:** Uses conversational tone (second person 'you' or casual first person). Opens with a question, surprising fact, or bold claim. Includes at least one specific, concrete example showing attention's impact (e.g., 'The cat sat on the mat' translation accuracy). Under 600 words. No sentences longer than 25 words. Uses active voice predominantly.

## Criterion 4: expl_completeness
**Category:** coverage
**Max Points:** N/A
**Description:** Covers the essential pieces without going too deep
**Pass Condition:** Explains the context problem with specific example (e.g., long sentences losing meaning). Describes Q/K/V mechanism with clear roles for each component. Explains parallel processing advantage over sequential models. Mentions long-range dependency capability with concrete illustration. Does not cover implementation details like positional encoding or layer normalization.
