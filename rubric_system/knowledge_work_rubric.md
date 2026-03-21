# Knowledge Work Research Document Rubric

A comprehensive rubric for evaluating complex research documents, reports, analyses, and knowledge work artifacts that involve significant data gathering, source evaluation, and analytical synthesis.

**Version:** 1.0  
**Last Updated:** March 2026  
**Based On:** CRAAP Test (Currency, Relevance, Authority, Accuracy, Purpose), journalism triangulation standards, PLOS reporting standards, APA JARS, ISO 20252

---

## Quick Reference

| Category | Criteria Count | Max Points |
|----------|----------------|------------|
| Source Quality | 6 | 17 |
| Evidence & Claims | 5 | 14 |
| Data & Visualizations | 5 | 13 |
| Forward-Looking Statements | 4 | 11 |
| Document Structure | 4 | 10 |
| Professional Polish | 4 | 9 |
| **Total** | **28** | **74** |

**Scoring Thresholds:**
- **Pass:** ≥ 63 points (85%)
- **Conditional Pass:** 52-62 points (70-84%)
- **Fail:** < 52 points (< 70%)

---

## Category 1: Source Quality (17 points)

### src_001: Source Authority (Weight: 3 - Critical)
**Description:** Sources come from credible, authoritative entities qualified to speak on the topic.

**Pass Condition:**
- Primary sources are peer-reviewed publications, official government/institutional data, or recognized domain experts
- Author/organization credentials are identifiable and relevant to the topic
- Sources are not anonymous blogs, user-generated wikis, or content farms
- For expert quotes: credentials are stated (title, affiliation, relevant experience)
- Institutional sources have clear accountability (gov agencies, established research orgs, public companies)

**Scoring:**
| Score | Criteria |
|-------|----------|
| 3 | 100% of sources meet authority standards |
| 2 | ≥80% meet standards, minor gaps documented |
| 1 | 60-79% meet standards |
| 0 | <60% meet standards or authority not verifiable |

---

### src_002: Source Relevance (Weight: 3 - Critical)
**Description:** Sources directly address the document's claims and are topically appropriate.

**Pass Condition:**
- Each source directly supports the specific claim it's cited for
- No tangential sources used to pad citation count
- Source scope matches claim scope (don't cite macro reports for micro claims)
- Sources address the same population/context as the document's focus
- No "citation drift" (citing source for claim it doesn't actually support)

**Scoring:**
| Score | Criteria |
|-------|----------|
| 3 | All sources directly relevant with clear connection to claims |
| 2 | ≥90% sources clearly relevant |
| 1 | 75-89% sources relevant |
| 0 | <75% sources relevant or significant citation drift |

---

### src_003: Source Currency/Freshness (Weight: 3 - Critical)
**Description:** Sources are appropriately recent for the topic's rate of change.

**Pass Condition:**
- Fast-changing domains (tech, markets, policy): Sources < 2 years old for current state claims
- Medium-change domains (science, business): Sources < 5 years old
- Slow-change domains (history, foundational theory): Age appropriate to topic
- If older sources used, explicitly justified (seminal work, historical baseline)
- "As of" dates clearly stated for time-sensitive data
- No stale statistics presented as current

**Domain-Specific Thresholds:**
| Domain | Max Age for Current Claims |
|--------|---------------------------|
| AI/ML, crypto, social media | 12 months |
| Technology, markets, politics | 24 months |
| Medicine, science, regulation | 36 months |
| Business strategy, economics | 48 months |
| History, philosophy, fundamentals | Context-dependent |

---

### src_004: Source Diversity (Weight: 2 - High)
**Description:** Document draws from multiple independent source types to avoid single-perspective bias.

**Pass Condition:**
- Minimum 3 independent source types used (e.g., academic, industry, government, journalist)
- No single organization provides >40% of cited sources
- Both primary and secondary sources included where appropriate
- Conflicting viewpoints acknowledged when they exist
- Geographic/institutional diversity for global topics

---

### src_005: Source Triangulation (Weight: 3 - Critical)
**Description:** Key factual claims are validated by multiple independent sources.

**Pass Condition:**
- **Tier 1 Claims (load-bearing/headline):** Minimum 3 independent sources
- **Tier 2 Claims (supporting/context):** Minimum 2 independent sources
- **Tier 3 Claims (background/established):** 1 authoritative source acceptable
- Sources are genuinely independent (not citing each other, not from same organization)
- When sources conflict, discrepancy is noted and addressed

**Claim Tier Definitions:**
| Tier | Description | Min Sources |
|------|-------------|-------------|
| 1 | Central thesis, key statistics, controversial claims | 3 |
| 2 | Supporting evidence, secondary data points | 2 |
| 3 | Background facts, established consensus | 1 |

---

### src_006: Source Accessibility (Weight: 1 - Standard)
**Description:** Sources are accessible for verification and follow-up.

**Pass Condition:**
- URLs/DOIs provided for online sources
- Publication details sufficient to locate offline sources
- Paywalled sources noted as such
- No dead links (at time of publication)
- Data sources include access instructions if not publicly available

---

## Category 2: Evidence & Claims (14 points)

### evd_001: Claim-Evidence Alignment (Weight: 3 - Critical)
**Description:** Every significant claim is supported by appropriate evidence.

**Pass Condition:**
- No unsupported assertions for factual claims
- Evidence type matches claim type:
  - Quantitative claims → numerical data
  - Causal claims → experimental/quasi-experimental evidence
  - Trend claims → time-series data
  - Comparative claims → controlled comparisons
- Evidence is presented before or immediately after the claim it supports
- Reader can trace each claim to its supporting evidence

---

### evd_002: Evidence Strength Calibration (Weight: 3 - Critical)
**Description:** Claim confidence is calibrated to evidence strength.

**Pass Condition:**
- Strong claims ("X causes Y", "X will happen") backed by strong evidence (RCTs, meta-analyses, direct measurement)
- Moderate claims ("X is associated with Y", "X likely") acceptable with correlational/observational evidence
- Weak claims ("X may", "suggests") used when evidence is preliminary/limited
- Hedging language matches evidence quality
- No overstatement of findings beyond what evidence supports

**Evidence Strength Hierarchy:**
| Strength | Evidence Type | Claim Language |
|----------|---------------|----------------|
| Strong | Meta-analysis, RCT, direct measurement | "X causes", "X is", "definitively" |
| Moderate | Cohort studies, multiple observational | "X is associated", "likely", "evidence suggests" |
| Weak | Case studies, single source, preliminary | "may", "possibly", "initial findings" |
| Speculative | Expert opinion, logical inference | "could", "hypothetically", "if...then" |

---

### evd_003: Counter-Evidence Acknowledgment (Weight: 2 - High)
**Description:** Document acknowledges evidence that contradicts or complicates its thesis.

**Pass Condition:**
- Known counter-arguments or conflicting data are addressed
- Limitations of supporting evidence are noted
- Alternative interpretations of data are acknowledged where reasonable
- Document doesn't cherry-pick only favorable evidence
- Steelman of opposing view presented for controversial claims

---

### evd_004: Statistical Rigor (Weight: 3 - Critical)
**Description:** Statistical claims meet basic methodological standards.

**Pass Condition:**
- Sample sizes reported for survey/study data
- Confidence intervals or margins of error included for estimates
- Percentages include base numbers (N)
- Comparisons use appropriate baselines
- No misleading aggregations (Simpson's paradox risks addressed)
- Statistical significance vs. practical significance distinguished
- Correlation not implied as causation without justification

---

### evd_005: Quote & Paraphrase Integrity (Weight: 3 - Critical)
**Description:** Quoted and paraphrased material accurately represents source meaning.

**Pass Condition:**
- Direct quotes are verbatim and in context
- Paraphrases capture source's actual meaning
- Ellipses indicate omissions in quotes
- No quote mining or selective excerpting that distorts meaning
- Quotes attributed to correct speaker/source

---

## Category 3: Data & Visualizations (13 points)

### viz_001: Visualization Accuracy (Weight: 3 - Critical)
**Description:** Charts and graphs accurately represent the underlying data.

**Pass Condition:**
- Y-axis starts at zero for bar charts (or break clearly indicated)
- Scales are linear unless log scale is explicitly labeled and justified
- Area/volume representations are proportional to values
- Time series use consistent intervals
- No 3D effects that distort perception
- Pie charts sum to 100% (or noted if not)

**Common Violations:**
- Truncated axes exaggerating differences
- Inconsistent bin sizes in histograms
- Cherry-picked time windows
- Dual-axis charts with misaligned scales

---

### viz_002: Visualization Clarity (Weight: 3 - Critical)
**Description:** Visualizations are immediately comprehensible without extensive study.

**Pass Condition:**
- Declarative title states the takeaway (not just "Sales by Region")
- All axes labeled with units
- Legend present and positioned logically (or direct labeling used)
- Font size readable at expected display size
- Color-blind safe palette used
- WCAG 2.0 AA contrast standards met (4.5:1 for text)
- No chartjunk (unnecessary gridlines, 3D effects, decorative elements)

---

### viz_003: Appropriate Chart Selection (Weight: 2 - High)
**Description:** Chart type matches the data relationship being communicated.

**Pass Condition:**
| Data Relationship | Appropriate Chart |
|-------------------|-------------------|
| Comparison | Bar, column |
| Trend over time | Line |
| Part-to-whole | Stacked bar, treemap (not pie for >5 categories) |
| Distribution | Histogram, box plot |
| Correlation | Scatter plot |
| Ranking | Horizontal bar (sorted) |
| Geographic | Map (choropleth, symbol) |

**Chart type is wrong for data type → automatic fail**

---

### viz_004: Data Table Standards (Weight: 2 - High)
**Description:** Tables are formatted for readability and comprehension.

**Pass Condition:**
- Columns aligned consistently (numbers right-aligned, text left-aligned)
- Units specified in headers
- Thousands separators used for large numbers
- Consistent decimal places within columns
- Sorted meaningfully (not randomly)
- Row/column totals included where relevant
- Source noted below table

---

### viz_005: Novel/Custom Visualization Quality (Weight: 3 - Critical)
**Description:** Non-standard visualizations add value and are properly explained.

**Pass Condition:**
- Custom visualization choice is justified (standard chart inadequate)
- Reading instructions provided for unfamiliar chart types
- Interactive elements have clear affordances
- Annotations guide interpretation
- Visualization tells a story, not just displays data
- Novel approach genuinely illuminates data (not novelty for novelty's sake)

**Examples of justified novel visualizations:**
- Sankey diagrams for flow/transition data
- Beeswarm plots for distribution + individual points
- Small multiples for multi-dimensional comparisons
- Bump charts for ranking changes over time

---

## Category 4: Forward-Looking Statements (11 points)

### fwd_001: Hypothesis Framing (Weight: 3 - Critical)
**Description:** Predictions and forecasts are clearly distinguished from established facts.

**Pass Condition:**
- Future-looking statements explicitly labeled as predictions/hypotheses
- Confidence level indicated (high/medium/low or probability range)
- Time horizon specified for predictions
- Conditional language used ("if X then Y", "assuming Z")
- No predictions presented as certainties

**Required Labels:**
- "We predict...", "Our hypothesis is...", "We expect..."
- NOT: "X will happen", "By 2030, Y" (without qualifier)

---

### fwd_002: Assumption Transparency (Weight: 3 - Critical)
**Description:** Key assumptions underlying predictions are explicitly stated.

**Pass Condition:**
- Load-bearing assumptions listed and explained
- Assumptions are testable/falsifiable
- Sensitivity analysis provided for key assumptions (what if assumption is wrong?)
- Dependencies between assumptions noted
- Historical analogies used as basis are explicitly identified

**Required Elements:**
- List of key assumptions
- Rationale for each assumption
- Impact if assumption proves false

---

### fwd_003: Uncertainty Quantification (Weight: 3 - Critical)
**Description:** Predictions include appropriate uncertainty ranges.

**Pass Condition:**
- Point estimates accompanied by ranges (confidence intervals, min/max scenarios)
- Epistemic uncertainty (what we don't know) vs. aleatoric uncertainty (inherent randomness) distinguished where relevant
- Base rates provided for probability claims
- Multiple scenarios presented for high-uncertainty predictions
- "Tail risks" or black swan possibilities acknowledged

**Uncertainty Expression Standards:**
| Certainty Level | Expression |
|-----------------|------------|
| High confidence | X with 90% CI [Y-Z] |
| Medium confidence | Range: Y to Z, most likely ~X |
| Low confidence | Highly uncertain; scenarios A, B, C |
| Unknown | Cannot reliably estimate; key uncertainties are... |

---

### fwd_004: Prediction Track Record (Weight: 2 - High)
**Description:** Where applicable, prior predictions by the author/source are referenced.

**Pass Condition:**
- If author has made prior predictions in this domain, track record noted
- If methodology has been used before, historical accuracy discussed
- Forecasting model validated against holdout data where possible
- No hiding of prior incorrect predictions

---

## Category 5: Document Structure (10 points)

### str_001: Executive Summary Quality (Weight: 3 - Critical)
**Description:** Document opens with a clear, complete summary of key findings.

**Pass Condition:**
- BLUF (Bottom Line Up Front) in first paragraph
- All major conclusions represented in summary
- Summary stands alone (reader gets main points without reading full doc)
- Key numbers/findings included, not just topics
- Length appropriate (typically 5-10% of full document)

---

### str_002: Logical Flow (Weight: 3 - Critical)
**Description:** Document sections follow a logical progression.

**Pass Condition:**
- Claims build on each other without circular reasoning
- Background/context precedes analysis
- Evidence presented before conclusions drawn from it
- No forward references to unexplained concepts
- Transitions between sections are clear

**Standard Research Doc Structure:**
1. Executive Summary / BLUF
2. Background / Context
3. Methodology (if applicable)
4. Findings / Analysis
5. Discussion / Implications
6. Recommendations (if applicable)
7. Limitations
8. Appendix / References

---

### str_003: Section Completeness (Weight: 2 - High)
**Description:** All necessary sections are present and complete.

**Pass Condition:**
- Methodology section present for original research/analysis
- Limitations section explicitly addresses gaps
- References/bibliography complete and consistent
- Appendices for detailed data that would interrupt flow
- Glossary for technical terms (if needed for audience)

---

### str_004: Audience Calibration (Weight: 2 - High)
**Description:** Technical depth and language match intended audience.

**Pass Condition:**
- Technical jargon defined or avoided based on audience
- Detail level appropriate (executive summary for leadership, full methodology for peers)
- Visual complexity matches audience sophistication
- Assumes appropriate baseline knowledge (not over- or under-explaining)

---

## Category 6: Professional Polish (9 points)

### pol_001: Citation Format Consistency (Weight: 2 - High)
**Description:** Citations follow a consistent format throughout.

**Pass Condition:**
- Single citation style used throughout (APA, Chicago, MLA, or house style)
- In-text citations match bibliography entries
- All cited works appear in references
- All references are cited in text
- URLs accessed dates included for web sources

---

### pol_002: Writing Quality (Weight: 3 - Critical)
**Description:** Prose is clear, concise, and professional.

**Pass Condition:**
- No grammatical or spelling errors
- Sentences are clear and parseable
- Passive voice used sparingly and intentionally
- Jargon minimized; necessary terms defined
- Consistent terminology (same concept = same word throughout)
- Appropriate formality level for context

---

### pol_003: Formatting Consistency (Weight: 2 - High)
**Description:** Visual formatting is consistent throughout the document.

**Pass Condition:**
- Heading hierarchy consistent (H1 > H2 > H3)
- Font sizes/styles consistent by element type
- Spacing consistent between sections
- List formatting consistent (bullets vs. numbers used consistently)
- Figure/table numbering sequential

---

### pol_004: Accessibility (Weight: 2 - High)
**Description:** Document is accessible to users with disabilities.

**Pass Condition:**
- Alt text for images/charts
- Proper heading structure (not just bold text)
- Color not sole means of conveying information
- Sufficient contrast ratios
- Screen reader compatible structure

---

## Scoring Examples

### Example 1: AI Industry Analysis Report

**Context:** 25-page report on AI chip market dynamics for VC audience

| Criterion | Score | Evidence |
|-----------|-------|----------|
| src_001 Authority | 3/3 | Uses SemiAnalysis, company 10-Ks, academic papers |
| src_002 Relevance | 3/3 | All sources directly address chip architecture, supply chain |
| src_003 Currency | 3/3 | 90% sources from 2025; older ones are seminal (Huang's Law) |
| src_004 Diversity | 2/2 | Mix of industry analysts, academic, company filings, journalism |
| src_005 Triangulation | 2/3 | Most claims have 2+ sources; TAM figures only from 1 analyst |
| src_006 Accessibility | 1/1 | All links working, DOIs provided |
| evd_001 Claim-Evidence | 3/3 | Each market share claim has direct data |
| evd_002 Strength Calibration | 2/3 | Some "will" claims based on analyst projections (moderate evidence) |
| evd_003 Counter-Evidence | 2/2 | Addresses bull and bear cases |
| evd_004 Statistical Rigor | 3/3 | Sample sizes, CIs, base rates included |
| evd_005 Quote Integrity | 3/3 | CEO quotes properly contextualized |
| viz_001 Accuracy | 3/3 | All charts start at zero, scales consistent |
| viz_002 Clarity | 2/3 | Most charts clear; one revenue chart has tiny labels |
| viz_003 Chart Selection | 2/2 | Line for trends, bar for comparisons |
| viz_004 Tables | 2/2 | Clean formatting, sorted by revenue |
| viz_005 Novel Viz | 2/3 | Sankey diagram for supply chain helpful but needs more annotation |
| fwd_001 Hypothesis Framing | 3/3 | "We project" language, confidence levels stated |
| fwd_002 Assumptions | 2/3 | Key assumptions listed; sensitivity analysis incomplete |
| fwd_003 Uncertainty | 3/3 | Bull/base/bear scenarios with ranges |
| fwd_004 Track Record | 1/2 | Author's prior accuracy not discussed |
| str_001 Exec Summary | 3/3 | BLUF with key numbers in first paragraph |
| str_002 Logical Flow | 3/3 | Market context → supply → demand → forecast |
| str_003 Section Completeness | 2/2 | All sections present including limitations |
| str_004 Audience Calibration | 2/2 | VC-appropriate depth |
| pol_001 Citations | 2/2 | Consistent format |
| pol_002 Writing | 3/3 | Clear, professional prose |
| pol_003 Formatting | 2/2 | Consistent throughout |
| pol_004 Accessibility | 1/2 | Missing alt text on some charts |

**Total Score: 65/74 (87.8%)** — Pass

---

### Example 2: Healthcare Policy Brief (Failing Example)

**Context:** 10-page brief on drug pricing reform for legislative staff

| Criterion | Score | Evidence |
|-----------|-------|----------|
| src_001 Authority | 1/3 | Heavy reliance on advocacy org reports, few peer-reviewed |
| src_002 Relevance | 2/3 | Some sources tangential to specific policy being discussed |
| src_003 Currency | 1/3 | Drug pricing data from 2019; landscape changed significantly |
| src_004 Diversity | 1/2 | 70% sources from single advocacy coalition |
| src_005 Triangulation | 1/3 | Key cost savings claim from single model |
| src_006 Accessibility | 1/1 | Links functional |
| evd_001 Claim-Evidence | 1/3 | "Will reduce costs by 40%" unsupported by methodology |
| evd_002 Strength Calibration | 0/3 | Strong claims ("will", "definitively") with weak evidence |
| evd_003 Counter-Evidence | 0/2 | Industry arguments dismissed without engagement |
| evd_004 Statistical Rigor | 1/3 | Percentages without base Ns; no CIs |
| evd_005 Quote Integrity | 2/3 | One quote taken out of context |
| viz_001 Accuracy | 2/3 | One bar chart with truncated axis |
| viz_002 Clarity | 2/3 | Charts readable but missing units on one axis |
| viz_003 Chart Selection | 2/2 | Appropriate choices |
| viz_004 Tables | 1/2 | Inconsistent number formatting |
| viz_005 Novel Viz | 0/3 | Timeline graphic confusing without explanation |
| fwd_001 Hypothesis Framing | 0/3 | Predictions stated as facts ("will save $X billion") |
| fwd_002 Assumptions | 0/3 | Assumptions not stated |
| fwd_003 Uncertainty | 0/3 | No ranges or scenarios provided |
| fwd_004 Track Record | 0/2 | N/A |
| str_001 Exec Summary | 2/3 | Summary present but missing key numbers |
| str_002 Logical Flow | 2/3 | Some sections out of order |
| str_003 Section Completeness | 1/2 | No limitations section |
| str_004 Audience Calibration | 2/2 | Appropriate for staff audience |
| pol_001 Citations | 1/2 | Inconsistent format |
| pol_002 Writing | 2/3 | Some unclear sentences |
| pol_003 Formatting | 2/2 | Consistent |
| pol_004 Accessibility | 1/2 | Missing alt text |

**Total Score: 31/74 (41.9%)** — Fail

**Key Issues:**
1. Source quality cluster fails (6/17 = 35%)
2. Forward-looking claims presented as certainties
3. No acknowledgment of counter-evidence or uncertainty

---

## Using This Rubric

### For Authors (Pre-Submission Checklist)

**Before finalizing your document:**

□ **Sources:** Can you defend the authority/currency of every source?  
□ **Triangulation:** Do your key claims have 3+ independent sources?  
□ **Evidence:** Is each claim supported by appropriately strong evidence?  
□ **Visualizations:** Would a first-time reader understand every chart in <10 seconds?  
□ **Predictions:** Are forecasts clearly labeled with uncertainty ranges?  
□ **Structure:** Could someone read only the exec summary and get the key points?  
□ **Polish:** Has someone else proofread for errors?

### For Reviewers (Quick Evaluation)

**Critical criteria (must all pass for document approval):**
- src_001, src_002, src_003, src_005 (Source quality)
- evd_001, evd_002, evd_004, evd_005 (Evidence quality)
- viz_001, viz_002 (Visualization accuracy)
- fwd_001, fwd_002, fwd_003 (Forward-looking statements)
- str_001, str_002 (Structure)
- pol_002 (Writing quality)

If any critical criterion scores 0, document requires major revision regardless of total score.

### Domain-Specific Adjustments

| Domain | Emphasis | De-Emphasis |
|--------|----------|-------------|
| Academic research | Statistical rigor, methodology, peer-reviewed sources | Executive summary, audience calibration |
| Business strategy | Forward-looking, exec summary, visualizations | Academic citations, statistical notation |
| Journalism | Source triangulation, quote integrity, currency | Uncertainty quantification, methodology |
| Policy briefs | Counter-evidence, assumption transparency | Novel visualizations, statistical notation |
| Technical documentation | Accuracy, completeness, accessibility | Predictions, narrative flow |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | March 2026 | Initial release |

---

## References

- CRAAP Test (Blakeslee, 2004) - California State University, Chico
- PLOS ONE Best Practices in Research Reporting
- APA Journal Article Reporting Standards (JARS)
- ISO 20252: Market, Opinion and Social Research
- Urban Institute Data Visualization Style Guide
- Edward Tufte's principles on graphical integrity
- Journalism source triangulation standards
- WCAG 2.0 Accessibility Guidelines
