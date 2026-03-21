#!/usr/bin/env python3
"""
Sample Rubrics — 10 task-specific rubrics demonstrating the scoring system's range.

Each rubric uses the canonical v4 models and scoring methods to evaluate
diverse output types: emails, code, summaries, SQL, arguments, schemas,
explanations, naming, scripts, and investment memos.

Usage:
    from rubric_system.sample_rubrics import ALL_SAMPLE_RUBRICS, build_rubric_for_task
    rubric = build_rubric_for_task(1)  # Cold outreach email
    rubric = ALL_SAMPLE_RUBRICS[0]()   # Same thing
"""

from rubric_system.models import (
    ScoringMethod,
    SubAttribute,
    ScoringRubric,
    Criterion,
    Rubric,
)


# ============================================================================
# Reusable scoring rubric factories (task-agnostic)
# ============================================================================

def _weighted(max_pts: int, subs: list[tuple[str, str, float, str]]) -> ScoringRubric:
    """Shorthand for WEIGHTED_COMPONENTS rubric."""
    return ScoringRubric(
        method=ScoringMethod.WEIGHTED_COMPONENTS,
        max_points=max_pts,
        sub_attributes=[
            SubAttribute(sub_id=s[0], description=s[1], weight=s[2], measurement=s[3])
            for s in subs
        ],
    )


def _penalty(max_pts: int, penalties: dict[str, float]) -> ScoringRubric:
    """Shorthand for PENALTY_BASED rubric."""
    return ScoringRubric(
        method=ScoringMethod.PENALTY_BASED,
        max_points=max_pts,
        penalties=penalties,
    )


def _binary(max_pts: int = 3) -> ScoringRubric:
    """Shorthand for BINARY rubric."""
    return ScoringRubric(method=ScoringMethod.BINARY, max_points=max_pts)


# ============================================================================
# Task 1: Cold Outreach Email to Series A Founder
# ============================================================================

def build_cold_outreach_email_rubric() -> Rubric:
    task = "Write a cold outreach email to a Series A founder pitching angel investment"

    criteria = [
        Criterion(
            id="email_subject",
            category="engagement",
            description="Subject line is compelling and specific — not generic or spammy",
            pass_condition="Subject is <60 chars, references something specific to the recipient, "
                          "creates curiosity without clickbait. No 'Quick question' or 'Touching base'.",
            scoring=_weighted(10, [
                ("specificity", "References recipient's company/round/domain", 0.40,
                 "1.0 if names company or specific context, 0.0 if generic"),
                ("brevity", "Under 60 chars, scannable on mobile", 0.25,
                 "1.0 if ≤60 chars, 0.5 if ≤80, 0.0 if >80"),
                ("curiosity_hook", "Creates reason to open without being clickbait", 0.35,
                 "1.0 if compelling + honest, 0.5 if generic, 0.0 if spammy"),
            ]),
            pass_examples=["'$2M angel check for Acme's Series A — operator background in logistics'"],
            fail_examples=["'Quick question'", "'Exciting investment opportunity!'"],
        ),
        Criterion(
            id="email_opening",
            category="engagement",
            description="First sentence earns the right to the second — no throat-clearing",
            pass_condition="Opens with specific signal: why now, why them, what you noticed. "
                          "No 'I hope this finds you well' or self-introductions.",
            scoring=_penalty(8, {
                "generic_greeting": -3.0,
                "self_intro_first": -2.0,
                "no_specific_signal": -2.0,
                "too_long_opening": -1.5,
            }),
            pass_examples=["'Saw your Techcrunch piece on [X] — the way you're attacking [problem] maps to what I built at [company]'"],
            fail_examples=["'Hi, my name is Tim and I'm an angel investor...'"],
        ),
        Criterion(
            id="email_value_prop",
            category="persuasion",
            description="Clearly articulates what the angel brings beyond capital",
            pass_condition="Specific operational value: domain expertise, network, customer intros, "
                          "hiring help. Concrete, not vague ('I can help').",
            scoring=_weighted(10, [
                ("specificity", "Names concrete value (intros, expertise, past wins)", 0.45,
                 "1.0 if 2+ specific offerings, 0.5 if 1 vague, 0.0 if just capital"),
                ("relevance", "Value prop maps to recipient's actual needs/stage", 0.35,
                 "1.0 if clearly relevant to their domain/stage, 0.0 if generic"),
                ("credibility", "Claims are verifiable (named companies, outcomes)", 0.20,
                 "1.0 if verifiable claims, 0.5 if plausible, 0.0 if unsubstantiated"),
            ]),
            pass_examples=["'I scaled logistics ops from $5M to $80M ARR at ShipCo — happy to open my network of 20+ VP Supply Chain contacts'"],
            fail_examples=["'I bring smart capital and strategic value to my portfolio companies'"],
        ),
        Criterion(
            id="email_social_proof",
            category="credibility",
            description="Establishes credibility without bragging",
            pass_condition="1-2 relevant proof points: portfolio wins, operating background, "
                          "mutual connections. Woven in, not a resume dump.",
            scoring=_weighted(8, [
                ("proof_quality", "Proof points are relevant and impressive", 0.50,
                 "1.0 if directly relevant wins, 0.5 if tangential, 0.0 if absent"),
                ("restraint", "1-2 points, not a resume dump", 0.30,
                 "1.0 if 1-2 tight proof points, 0.5 if 3-4, 0.0 if resume paragraph"),
                ("natural_integration", "Proof woven into narrative, not listed", 0.20,
                 "1.0 if organic, 0.0 if bullet-pointed credentials"),
            ]),
            pass_examples=["'...when I was CTO at [X] (acq. by Google), we solved a similar cold-start problem'"],
            fail_examples=["'I have 15 years of experience, 30 investments, board seats at...'"],
        ),
        Criterion(
            id="email_cta",
            category="conversion",
            description="Call to action is low-friction and specific",
            pass_condition="Single, clear ask. Low commitment (15-min call, not 'let's meet'). "
                          "Suggests specific times or next step.",
            scoring=_weighted(8, [
                ("clarity", "Single unambiguous ask", 0.35,
                 "1.0 if one clear ask, 0.5 if implied, 0.0 if multiple/confusing"),
                ("low_friction", "Minimal commitment required", 0.35,
                 "1.0 if 15-min call or async, 0.5 if meeting, 0.0 if big ask"),
                ("specificity", "Includes proposed time or concrete next step", 0.30,
                 "1.0 if specific availability, 0.5 if 'sometime this week', 0.0 if open-ended"),
            ]),
            pass_examples=["'Free for a 15-min call Thursday or Friday afternoon? Happy to share my thesis on [space] first over email if you prefer.'"],
            fail_examples=["'Let me know if you're interested in chatting sometime.'"],
        ),
        Criterion(
            id="email_tone",
            category="voice",
            description="Tone is peer-to-peer, confident but not presumptuous",
            pass_condition="Reads like one founder talking to another. Not sycophantic, not salesy, "
                          "not formal. Respects their time.",
            scoring=_penalty(6, {
                "sycophantic_language": -2.0,
                "salesy_pressure": -2.0,
                "overly_formal": -1.5,
                "presumptuous_familiarity": -1.5,
                "humble_brag": -1.0,
            }),
            pass_examples=["Direct, warm, brief — reads like a text from a smart friend"],
            fail_examples=["'I'd be truly honored to be part of your incredible journey'"],
        ),
        Criterion(
            id="email_length",
            category="structure",
            description="Email is scannable in <30 seconds — under 150 words",
            pass_condition="Under 150 words. Short paragraphs (1-3 sentences). "
                          "White space between blocks. No walls of text.",
            scoring=_weighted(6, [
                ("word_count", "Under 150 words total", 0.50,
                 "1.0 if ≤150, 0.7 if ≤200, 0.3 if ≤250, 0.0 if >250"),
                ("scannability", "Short paragraphs, visual breaks", 0.50,
                 "1.0 if all paragraphs ≤3 sentences with breaks, 0.0 if wall of text"),
            ]),
            pass_examples=["5 short paragraphs, 120 words total"],
            fail_examples=["3 dense paragraphs, 300+ words"],
        ),
    ]

    return Rubric(
        task=task,
        domain="cold_outreach_email",
        criteria=criteria,
        total_points=sum(c.scoring.max_points for c in criteria),
        pass_threshold=0.80,
    )


# ============================================================================
# Task 2: Python CSV Parser
# ============================================================================

def build_csv_parser_rubric() -> Rubric:
    task = "Generate a Python function that parses messy CSV data with inconsistent delimiters and missing headers"

    criteria = [
        Criterion(
            id="code_correctness",
            category="functionality",
            description="Function handles the stated requirements: inconsistent delimiters, missing headers",
            pass_condition="Detects and handles comma/tab/pipe/semicolon delimiters. "
                          "Generates synthetic headers when missing. Doesn't crash on edge cases.",
            scoring=_weighted(12, [
                ("delimiter_detection", "Auto-detects or handles multiple delimiter types", 0.35,
                 "1.0 if auto-detects from data, 0.5 if parameterized, 0.0 if hardcoded"),
                ("header_handling", "Generates headers when missing, detects when present", 0.35,
                 "1.0 if auto-detects + generates, 0.5 if one or other, 0.0 if assumes headers"),
                ("edge_case_resilience", "Handles empty rows, mixed quoting, trailing delimiters", 0.30,
                 "% of edge cases handled without crash"),
            ]),
            pass_examples=["Uses csv.Sniffer for delimiter detection, heuristic for header presence"],
            fail_examples=["Hardcodes comma delimiter, assumes first row is header"],
        ),
        Criterion(
            id="code_robustness",
            category="reliability",
            description="Graceful error handling, doesn't silently corrupt data",
            pass_condition="Try/except with meaningful errors. Logs warnings for skipped rows. "
                          "Returns structured result with metadata (rows parsed, rows skipped, issues found).",
            scoring=_weighted(10, [
                ("error_handling", "Catches and reports errors meaningfully", 0.40,
                 "1.0 if structured error reporting, 0.5 if basic try/except, 0.0 if bare"),
                ("data_integrity", "Never silently drops or corrupts data", 0.35,
                 "1.0 if reports all anomalies, 0.0 if silently swallows"),
                ("return_metadata", "Returns parse stats (rows, skips, warnings)", 0.25,
                 "1.0 if structured result object, 0.5 if just data, 0.0 if raw list"),
            ]),
            pass_examples=["Returns ParseResult(data=..., warnings=[...], rows_skipped=2)"],
            fail_examples=["Bare except: pass, returns partial data silently"],
        ),
        Criterion(
            id="code_api_design",
            category="usability",
            description="Function signature is clean, well-typed, with sensible defaults",
            pass_condition="Type hints. Docstring with examples. Reasonable defaults. "
                          "Accepts str | Path | IO. Returns typed structure (not raw list).",
            scoring=_weighted(8, [
                ("type_hints", "Full type annotations on params and return", 0.35,
                 "1.0 if complete, 0.5 if partial, 0.0 if none"),
                ("docstring", "Docstring with description, args, returns, example", 0.30,
                 "1.0 if complete with example, 0.5 if basic, 0.0 if missing"),
                ("input_flexibility", "Accepts file path, string, or file object", 0.35,
                 "1.0 if multiple input types, 0.5 if one type, 0.0 if unclear"),
            ]),
            pass_examples=["def parse_csv(source: str | Path | IO, ...) -> ParseResult:"],
            fail_examples=["def parse(f):  # no types, no docs"],
        ),
        Criterion(
            id="code_idiomaticness",
            category="quality",
            description="Uses Python idioms and stdlib appropriately",
            pass_condition="Uses csv module (not regex-only). Leverages csv.Sniffer. "
                          "Dataclasses or TypedDict for results. No reinventing wheels.",
            scoring=_penalty(8, {
                "reinvents_csv_module": -3.0,
                "regex_only_parsing": -2.0,
                "no_type_structures": -1.5,
                "mutable_default_args": -1.5,
                "global_state": -2.0,
            }),
            pass_examples=["Builds on csv.reader/csv.Sniffer, returns dataclass"],
            fail_examples=["Regex-only CSV parsing, returns list of dicts with no structure"],
        ),
        Criterion(
            id="code_testability",
            category="quality",
            description="Code is structured for easy testing",
            pass_condition="Pure function (no side effects). Includes or suggests test cases. "
                          "Small composable helpers, not one monolith.",
            scoring=_weighted(6, [
                ("pure_function", "No side effects, deterministic", 0.40,
                 "1.0 if pure, 0.5 if minor side effects (logging ok), 0.0 if writes files"),
                ("modularity", "Logic decomposed into testable helpers", 0.30,
                 "1.0 if 3+ focused helpers, 0.5 if 2, 0.0 if monolith"),
                ("test_examples", "Includes example test cases or assertions", 0.30,
                 "1.0 if test cases included, 0.5 if doctest, 0.0 if none"),
            ]),
            pass_examples=["Separate detect_delimiter(), detect_headers(), parse_rows() + tests"],
            fail_examples=["Single 80-line function with no tests"],
        ),
    ]

    return Rubric(
        task=task,
        domain="code_generation",
        criteria=criteria,
        total_points=sum(c.scoring.max_points for c in criteria),
        pass_threshold=0.85,
    )


# ============================================================================
# Task 3: Executive Summary from Technical Blog Post
# ============================================================================

def build_exec_summary_rubric() -> Rubric:
    task = "Summarize a 2,000-word technical blog post into a 3-bullet executive summary"

    criteria = [
        Criterion(
            id="sum_compression",
            category="structure",
            description="Achieves 20:1+ compression — exactly 3 bullets, each 1-2 sentences",
            pass_condition="Exactly 3 bullets. Each bullet is 1-2 sentences. "
                          "Total under 100 words. No filler or hedging.",
            scoring=_weighted(10, [
                ("bullet_count", "Exactly 3 bullets", 0.30,
                 "1.0 if exactly 3, 0.5 if 2 or 4, 0.0 if other"),
                ("bullet_density", "Each bullet is 1-2 sentences, no filler", 0.35,
                 "% of bullets that are 1-2 tight sentences"),
                ("total_length", "Total under 100 words", 0.35,
                 "1.0 if ≤100 words, 0.7 if ≤130, 0.3 if ≤160, 0.0 if >160"),
            ]),
            pass_examples=["3 bullets, 85 words total, each bullet one declarative sentence + one supporting"],
            fail_examples=["5 bullets, 200 words, mini-paragraphs disguised as bullets"],
        ),
        Criterion(
            id="sum_fidelity",
            category="accuracy",
            description="Bullets capture the actual thesis and key claims — no hallucination",
            pass_condition="Bullet 1 = core thesis/finding. Bullet 2 = key evidence or mechanism. "
                          "Bullet 3 = implication or so-what. All traceable to source text.",
            scoring=_weighted(12, [
                ("thesis_capture", "First bullet nails the core thesis", 0.40,
                 "1.0 if captures central claim, 0.5 if tangential, 0.0 if wrong"),
                ("evidence_capture", "Key supporting evidence or mechanism included", 0.30,
                 "1.0 if strongest evidence cited, 0.5 if secondary, 0.0 if missing"),
                ("no_hallucination", "Nothing claimed that isn't in the source", 0.30,
                 "1.0 if all claims traceable, 0.0 per hallucinated claim"),
            ]),
            pass_examples=["Thesis + strongest data point + strategic implication, all from source"],
            fail_examples=["Vague paraphrase that could describe any post on the topic"],
        ),
        Criterion(
            id="sum_exec_value",
            category="utility",
            description="An executive could make a decision or take action from these 3 bullets alone",
            pass_condition="Answers 'so what?' and 'what do I do with this?'. Quantifies where possible. "
                          "Uses declarative framing, not passive/descriptive.",
            scoring=_weighted(10, [
                ("actionability", "Reader knows what to do or think differently after reading", 0.40,
                 "1.0 if clear action/decision implication, 0.5 if informational, 0.0 if academic"),
                ("quantification", "Numbers, magnitudes, or concrete specifics included", 0.30,
                 "1.0 if key numbers preserved, 0.5 if qualitative only, 0.0 if vague"),
                ("declarative_framing", "Bullets state claims, not 'the post discusses...'", 0.30,
                 "1.0 if all declarative, 0.5 if mixed, 0.0 if all descriptive/passive"),
            ]),
            pass_examples=["'LLM inference costs dropped 90% in 18 months — implications for build-vs-buy decisions in 2026'"],
            fail_examples=["'The author discusses various aspects of LLM cost trends'"],
        ),
        Criterion(
            id="sum_standalone",
            category="clarity",
            description="Summary is self-contained — no context needed to understand it",
            pass_condition="Doesn't reference 'the post' or 'the author'. Defines any jargon. "
                          "A reader with no context gets the point.",
            scoring=_penalty(6, {
                "references_source": -2.0,
                "undefined_jargon": -1.5,
                "assumes_context": -1.5,
                "passive_voice_dominant": -1.0,
            }),
            pass_examples=["Self-contained claims that work as standalone intelligence"],
            fail_examples=["'The author argues that...' or 'This post explores...'"],
        ),
    ]

    return Rubric(
        task=task,
        domain="summarization",
        criteria=criteria,
        total_points=sum(c.scoring.max_points for c in criteria),
        pass_threshold=0.85,
    )


# ============================================================================
# Task 4: SQL Query — Top 10 Customers by LTV
# ============================================================================

def build_sql_ltv_rubric() -> Rubric:
    task = "Create a SQL query to find the top 10 customers by lifetime value excluding refunds, from a schema you define"

    criteria = [
        Criterion(
            id="sql_schema",
            category="design",
            description="Schema is realistic, normalized, and supports the query requirements",
            pass_condition="Separate customers, orders, order_items, payments/refunds tables. "
                          "Proper PKs/FKs. Realistic column types. Refunds modeled distinctly from payments.",
            scoring=_weighted(10, [
                ("normalization", "Proper 3NF with PKs/FKs", 0.30,
                 "1.0 if 3NF, 0.5 if some denormalization, 0.0 if flat"),
                ("refund_modeling", "Refunds modeled as distinct records, not negative amounts", 0.35,
                 "1.0 if refund table or refund_type flag, 0.5 if negative amounts, 0.0 if not modeled"),
                ("realistic_columns", "Realistic types, constraints, timestamps", 0.35,
                 "% of tables with appropriate types and constraints"),
            ]),
            pass_examples=["customers, orders, order_items, payments (with type: 'charge'|'refund') + indexes"],
            fail_examples=["Single 'transactions' table with all data flattened"],
        ),
        Criterion(
            id="sql_correctness",
            category="functionality",
            description="Query returns correct results — top 10 by LTV excluding refunds",
            pass_condition="Correctly aggregates payments minus refunds per customer. "
                          "Uses proper GROUP BY, HAVING, ORDER BY DESC LIMIT 10. "
                          "Handles NULL edge cases.",
            scoring=_weighted(12, [
                ("aggregation_logic", "SUM(charges) - SUM(refunds) or equivalent", 0.40,
                 "1.0 if correct LTV calc, 0.5 if close, 0.0 if wrong"),
                ("grouping", "Proper GROUP BY customer with ORDER BY + LIMIT", 0.30,
                 "1.0 if correct, 0.0 if missing or wrong"),
                ("null_handling", "COALESCE or equivalent for customers with no refunds", 0.30,
                 "1.0 if handles nulls, 0.5 if partially, 0.0 if would fail on nulls"),
            ]),
            pass_examples=["COALESCE(SUM(CASE WHEN type='charge' THEN amount END), 0) - COALESCE(SUM(CASE WHEN type='refund' THEN amount END), 0)"],
            fail_examples=["SELECT * FROM customers ORDER BY amount — no aggregation"],
        ),
        Criterion(
            id="sql_readability",
            category="quality",
            description="Query is well-formatted, commented, and uses CTEs appropriately",
            pass_condition="Uses CTEs for complex subqueries. Consistent formatting. "
                          "Meaningful aliases. Comments on non-obvious logic.",
            scoring=_weighted(8, [
                ("cte_usage", "Uses CTEs for readability instead of nested subqueries", 0.35,
                 "1.0 if CTEs for distinct logical steps, 0.5 if inline subqueries, 0.0 if spaghetti"),
                ("formatting", "Consistent capitalization, indentation, line breaks", 0.30,
                 "1.0 if clean formatting, 0.5 if mostly ok, 0.0 if unformatted"),
                ("documentation", "Comments on key logic, meaningful aliases", 0.35,
                 "1.0 if commented + good aliases, 0.5 if one, 0.0 if neither"),
            ]),
            pass_examples=["WITH customer_charges AS (...), customer_refunds AS (...) SELECT ..."],
            fail_examples=["One-liner with nested subqueries and single-letter aliases"],
        ),
        Criterion(
            id="sql_performance",
            category="optimization",
            description="Query would perform well at scale (millions of rows)",
            pass_condition="Suggests or includes appropriate indexes. Avoids SELECT *. "
                          "Doesn't use correlated subqueries. Notes on execution plan.",
            scoring=_penalty(6, {
                "select_star": -1.5,
                "correlated_subquery": -2.0,
                "missing_index_suggestion": -1.0,
                "cartesian_join_risk": -2.5,
                "function_on_indexed_column": -1.0,
            }),
            pass_examples=["Index on payments(customer_id, type, amount), avoids correlated subqueries"],
            fail_examples=["SELECT * with correlated subquery per customer row"],
        ),
    ]

    return Rubric(
        task=task,
        domain="sql_query",
        criteria=criteria,
        total_points=sum(c.scoring.max_points for c in criteria),
        pass_threshold=0.85,
    )


# ============================================================================
# Task 5: Counterargument — AGI Before 2030
# ============================================================================

def build_counterargument_rubric() -> Rubric:
    task = "Write a counterargument to the claim 'AGI will arrive before 2030'"

    criteria = [
        Criterion(
            id="arg_steelman",
            category="intellectual_honesty",
            description="Steelmans the original claim before countering it",
            pass_condition="First paragraph presents the strongest version of the AGI-by-2030 case. "
                          "Cites real scaling results, benchmarks, expert proponents. "
                          "Shows the reader you understand why smart people believe this.",
            scoring=_weighted(10, [
                ("steelman_quality", "Presents strongest version of the claim", 0.50,
                 "1.0 if cites specific results/proponents, 0.5 if generic, 0.0 if strawman"),
                ("specific_evidence", "References real benchmarks, papers, or expert positions", 0.30,
                 "1.0 if 2+ specific references, 0.5 if 1, 0.0 if none"),
                ("good_faith", "Reader feels the argument was fairly represented", 0.20,
                 "1.0 if fair, 0.0 if dismissive/strawman"),
            ]),
            pass_examples=["'The case for AGI by 2030 is stronger than critics admit: GPT-4 to o3 showed...'"],
            fail_examples=["'Some people naively believe AGI is coming soon, but...'"],
        ),
        Criterion(
            id="arg_counter_quality",
            category="argumentation",
            description="Counterarguments are specific, non-obvious, and empirically grounded",
            pass_condition="3+ distinct counter-threads. At least one challenges the definition of AGI. "
                          "At least one is empirical (benchmarking issues, capability gaps). "
                          "At least one is structural (alignment, deployment, regulation).",
            scoring=_weighted(12, [
                ("argument_count", "3+ distinct counter-threads", 0.20,
                 "1.0 if 3+, 0.5 if 2, 0.0 if 1"),
                ("definitional_challenge", "Challenges what 'AGI' means and why it matters", 0.25,
                 "1.0 if substantive definitional argument, 0.0 if skips it"),
                ("empirical_grounding", "Cites specific capability gaps, benchmark limitations", 0.30,
                 "1.0 if specific gaps with evidence, 0.5 if general, 0.0 if hand-wavy"),
                ("structural_barriers", "Addresses alignment, regulation, deployment realities", 0.25,
                 "1.0 if specific structural argument, 0.5 if mentioned, 0.0 if absent"),
            ]),
            pass_examples=["Definitional ambiguity + benchmark saturation without real-world transfer + regulatory friction"],
            fail_examples=["'AI is overhyped' repeated three different ways"],
        ),
        Criterion(
            id="arg_nuance",
            category="sophistication",
            description="Avoids absolutism — acknowledges uncertainty and conditions",
            pass_condition="Uses probabilistic language. Identifies conditions under which the claim "
                          "could be true. Distinguishes 'narrow AGI' from 'transformative AI'. "
                          "Doesn't claim to know the answer.",
            scoring=_penalty(8, {
                "absolutist_claim": -2.5,
                "dismisses_without_evidence": -2.0,
                "ignores_counterexamples": -1.5,
                "no_uncertainty_acknowledgment": -2.0,
                "appeal_to_authority_only": -1.0,
            }),
            pass_examples=["'AGI by 2030 is possible but improbable — here's why the base rate for such predictions is poor'"],
            fail_examples=["'AGI will definitely not happen by 2030'"],
        ),
        Criterion(
            id="arg_readability",
            category="communication",
            description="Well-structured, scannable, persuasive prose",
            pass_condition="Clear thesis in first paragraph. Each counter-thread in its own section. "
                          "Conclusion synthesizes. Under 800 words.",
            scoring=_weighted(6, [
                ("structure", "Thesis → steelman → counters → synthesis", 0.40,
                 "1.0 if clear structure, 0.5 if partially organized, 0.0 if stream of consciousness"),
                ("concision", "Under 800 words, no padding", 0.30,
                 "1.0 if ≤800, 0.7 if ≤1000, 0.0 if >1200"),
                ("persuasive_flow", "Builds momentum, ends strong", 0.30,
                 "1.0 if compelling arc, 0.5 if flat, 0.0 if scattered"),
            ]),
            pass_examples=["700 words, clear sections, ends with a memorable reframe"],
            fail_examples=["1500-word stream of consciousness with no structure"],
        ),
    ]

    return Rubric(
        task=task,
        domain="argumentation",
        criteria=criteria,
        total_points=sum(c.scoring.max_points for c in criteria),
        pass_threshold=0.80,
    )


# ============================================================================
# Task 6: JSON Schema — Multi-tenant SaaS Billing
# ============================================================================

def build_billing_schema_rubric() -> Rubric:
    task = "Design a JSON schema for a multi-tenant SaaS billing system supporting usage-based and seat-based pricing"

    criteria = [
        Criterion(
            id="schema_completeness",
            category="design",
            description="Schema covers all required entities and pricing models",
            pass_condition="Entities: tenant, plan, subscription, usage_record, invoice, line_item. "
                          "Pricing models: per-seat, usage-based (metered), tiered, hybrid. "
                          "Billing cycles, proration, trial periods.",
            scoring=_weighted(12, [
                ("entity_coverage", "All required entities present", 0.30,
                 "% of required entities modeled (tenant, plan, subscription, usage, invoice, line_item)"),
                ("pricing_model_support", "Both seat-based and usage-based modeled", 0.35,
                 "1.0 if both + hybrid, 0.75 if both, 0.5 if one, 0.0 if neither"),
                ("billing_lifecycle", "Cycles, proration, trials, upgrades/downgrades", 0.35,
                 "% of lifecycle events modeled (create, upgrade, downgrade, cancel, prorate, trial)"),
            ]),
            pass_examples=["Plan with pricing_model: {type: 'hybrid', seat_price: ..., metered_dimensions: [...]}"],
            fail_examples=["Just 'plan' and 'subscription' with flat price field"],
        ),
        Criterion(
            id="schema_correctness",
            category="quality",
            description="Valid JSON Schema with proper types, constraints, references",
            pass_condition="Valid JSON Schema (draft-07+). Uses $ref for reuse. "
                          "Required fields marked. Enums for constrained values. "
                          "Proper date-time formats.",
            scoring=_weighted(10, [
                ("schema_validity", "Valid JSON Schema syntax", 0.30,
                 "1.0 if valid draft-07+, 0.5 if mostly valid, 0.0 if invalid"),
                ("ref_usage", "Uses $ref for reusable definitions", 0.25,
                 "1.0 if DRY with $ref, 0.5 if some reuse, 0.0 if duplicated"),
                ("constraint_quality", "Proper enums, required, formats, patterns", 0.45,
                 "% of fields with appropriate constraints"),
            ]),
            pass_examples=["$ref to shared 'money' type with currency+amount, enum for billing_interval"],
            fail_examples=["Freeform JSON with no type constraints"],
        ),
        Criterion(
            id="schema_extensibility",
            category="architecture",
            description="Schema is extensible without breaking changes",
            pass_condition="Uses additionalProperties judiciously. Versioned. "
                          "Metered dimensions are a list (not hardcoded). "
                          "Custom metadata fields supported.",
            scoring=_weighted(8, [
                ("metered_extensibility", "Usage dimensions are dynamic, not hardcoded", 0.40,
                 "1.0 if array of dimension objects, 0.5 if a few named fields, 0.0 if hardcoded"),
                ("metadata_support", "Custom metadata/extension points", 0.30,
                 "1.0 if metadata object on key entities, 0.0 if closed"),
                ("versioning", "Schema version field or versioning strategy", 0.30,
                 "1.0 if versioned, 0.0 if not"),
            ]),
            pass_examples=["metered_dimensions: [{id, unit, tiers: [...]}] — add new dimensions without schema change"],
            fail_examples=["Hardcoded 'api_calls' and 'storage_gb' fields"],
        ),
        Criterion(
            id="schema_realworld",
            category="practicality",
            description="Schema reflects real billing system patterns (Stripe-informed, not academic)",
            pass_condition="Models concepts from real systems: idempotency keys, "
                          "invoice status lifecycle, webhook events, currency handling. "
                          "Avoids naive patterns (storing calculated totals without line items).",
            scoring=_penalty(8, {
                "no_currency_handling": -2.0,
                "calculated_total_without_line_items": -2.0,
                "no_idempotency": -1.0,
                "no_invoice_status_lifecycle": -1.5,
                "naive_date_handling": -1.5,
                "single_currency_assumption": -1.0,
            }),
            pass_examples=["Invoice with status enum (draft→open→paid→void), line_items array, currency code per amount"],
            fail_examples=["Invoice with just 'total: 99.99' and no line items"],
        ),
    ]

    return Rubric(
        task=task,
        domain="schema_design",
        criteria=criteria,
        total_points=sum(c.scoring.max_points for c in criteria),
        pass_threshold=0.85,
    )


# ============================================================================
# Task 7: Explain Transformer Attention to a 16-Year-Old
# ============================================================================

def build_explanation_rubric() -> Rubric:
    task = "Explain transformer attention mechanisms to a smart 16-year-old"

    criteria = [
        Criterion(
            id="expl_accuracy",
            category="correctness",
            description="Technical content is correct — no simplification-induced errors",
            pass_condition="Query/Key/Value framework explained correctly. "
                          "Dot product similarity is accurate. Softmax described correctly. "
                          "Multi-head attention's purpose is right.",
            scoring=_weighted(12, [
                ("qkv_correctness", "Q/K/V roles explained accurately", 0.35,
                 "1.0 if correct mechanism, 0.5 if metaphor-only, 0.0 if wrong"),
                ("attention_math", "Dot product + softmax pipeline correct", 0.35,
                 "1.0 if mechanism right, 0.5 if hand-wavy but directionally correct, 0.0 if wrong"),
                ("multihead_purpose", "Why multiple heads matter", 0.30,
                 "1.0 if explains different relationship types, 0.5 if mentions it, 0.0 if absent"),
            ]),
            pass_examples=["'Each word asks a question (query), advertises what it knows (key), and shares details (value)'"],
            fail_examples=["'Attention is when the model focuses on important words' — no mechanism"],
        ),
        Criterion(
            id="expl_accessibility",
            category="audience_fit",
            description="A smart 16-year-old actually understands it after reading",
            pass_condition="No unexplained jargon. Uses analogies from their world. "
                          "Builds from familiar concepts (search, recommendation) to new ones. "
                          "Math level: algebra ok, linear algebra explained if used.",
            scoring=_weighted(10, [
                ("jargon_handling", "All technical terms explained or avoided", 0.30,
                 "1.0 if all explained, 0.5 if most, 0.0 if jargon-heavy"),
                ("analogy_quality", "Uses relatable analogies (social media, school, etc.)", 0.35,
                 "1.0 if memorable analogy that maps correctly, 0.5 if generic, 0.0 if none"),
                ("progressive_complexity", "Builds from simple to complex", 0.35,
                 "1.0 if clear scaffold, 0.5 if some structure, 0.0 if jumps to hard parts"),
            ]),
            pass_examples=["Starts with 'imagine searching for a video on YouTube' → builds to Q/K/V"],
            fail_examples=["'Attention computes softmax(QK^T/√d_k)V' with no unpacking"],
        ),
        Criterion(
            id="expl_engagement",
            category="communication",
            description="Explanation is engaging — a 16-year-old would actually read to the end",
            pass_condition="Conversational tone. Not condescending. Includes a 'whoa' moment. "
                          "Under 600 words. Has a hook in the first sentence.",
            scoring=_weighted(8, [
                ("hook", "First sentence creates curiosity", 0.30,
                 "1.0 if compelling hook, 0.5 if adequate, 0.0 if textbook opening"),
                ("tone", "Conversational, not textbook or condescending", 0.35,
                 "1.0 if natural, 0.5 if slightly formal, 0.0 if textbook/patronizing"),
                ("concision", "Under 600 words, no padding", 0.35,
                 "1.0 if ≤600, 0.7 if ≤800, 0.0 if >1000"),
            ]),
            pass_examples=["'You know how autocomplete seems to read your mind? Here's the trick...'"],
            fail_examples=["'Attention mechanisms are a fundamental component of transformer architectures...'"],
        ),
        Criterion(
            id="expl_completeness",
            category="coverage",
            description="Covers the essential pieces without going too deep",
            pass_condition="Covers: why attention exists (context problem), how it works (Q/K/V), "
                          "why it matters (parallel processing, long-range dependencies). "
                          "Doesn't require covering positional encoding, layer norm, etc.",
            scoring=_weighted(6, [
                ("motivation", "Explains why attention was invented (the problem it solves)", 0.35,
                 "1.0 if clear problem statement, 0.5 if implied, 0.0 if jumps to mechanism"),
                ("mechanism", "How attention works at an intuitive level", 0.35,
                 "1.0 if clear mechanism, 0.0 if vague"),
                ("significance", "Why it matters / what it enabled", 0.30,
                 "1.0 if connects to real impact, 0.5 if mentioned, 0.0 if absent"),
            ]),
            pass_examples=["Problem (RNNs forget) → Mechanism (Q/K/V attention) → Impact (ChatGPT, translation)"],
            fail_examples=["Deep dive into multi-head attention math with no motivation"],
        ),
    ]

    return Rubric(
        task=task,
        domain="explanation",
        criteria=criteria,
        total_points=sum(c.scoring.max_points for c in criteria),
        pass_threshold=0.80,
    )


# ============================================================================
# Task 8: Startup Names — AI Contract Review
# ============================================================================

def build_naming_rubric() -> Rubric:
    task = "Generate 5 names for a startup that does AI-powered contract review for mid-market law firms"

    criteria = [
        Criterion(
            id="name_count",
            category="structure",
            description="Exactly 5 names provided, each with rationale",
            pass_condition="Exactly 5 names. Each has 1-2 sentence rationale explaining "
                          "the thinking behind it.",
            scoring=_binary(4),
            pass_examples=["5 names, each with explanation of etymology and positioning"],
            fail_examples=["3 names with no explanation, or 10 names dumped"],
        ),
        Criterion(
            id="name_memorability",
            category="quality",
            description="Names are memorable, pronounceable, and pass the 'phone test'",
            pass_condition="Each name: ≤3 syllables preferred, no awkward letter combos, "
                          "survives being spoken aloud, doesn't require spelling out.",
            scoring=_weighted(10, [
                ("pronounceability", "Names can be said aloud without confusion", 0.40,
                 "% of names that pass the phone test (say it, spell it)"),
                ("brevity", "Short, punchy — ideally ≤3 syllables", 0.30,
                 "% of names at ≤3 syllables"),
                ("distinctiveness", "Doesn't blend in with existing brands", 0.30,
                 "% of names that are distinct from obvious competitors"),
            ]),
            pass_examples=["'Clause' — 1 syllable, legal meaning, memorable"],
            fail_examples=["'IntelliLegalContractAI' — unmemorable, generic compound"],
        ),
        Criterion(
            id="name_domain_resonance",
            category="relevance",
            description="Names signal legal/contract/AI domain without being generic",
            pass_condition="Names evoke precision, trust, intelligence, or legal concepts. "
                          "Not generic 'AI' prefix/suffix spam. "
                          "Would feel at home on a law firm partner's desk.",
            scoring=_weighted(10, [
                ("domain_signal", "Evokes legal/contract/precision without being literal", 0.40,
                 "% of names with subtle domain resonance"),
                ("avoids_generic_ai", "No 'AI' prefix/suffix, no '-ify', no 'Smart[X]'", 0.30,
                 "% of names avoiding generic tech naming patterns"),
                ("trust_register", "Would a law firm partner take a meeting with this company?", 0.30,
                 "% of names that feel professional enough for legal market"),
            ]),
            pass_examples=["'Redline' — contract review term, implies precision and editing"],
            fail_examples=["'ContractAI', 'SmartReview', 'LegalBot'"],
        ),
        Criterion(
            id="name_availability",
            category="practicality",
            description="Names are likely available — .com plausible, not taken by major brands",
            pass_condition="At least 3/5 names have plausible .com availability (not common English words). "
                          "None are existing well-known brands. Notes on availability included.",
            scoring=_weighted(6, [
                ("domain_plausibility", "Names likely have .com available or reasonable variant", 0.50,
                 "% of names where .com is plausible (not a common English word)"),
                ("no_trademark_conflicts", "Not an existing well-known brand name", 0.50,
                 "% of names with no obvious trademark conflict"),
            ]),
            pass_examples=["'Clausebound' — coined word, .com likely available"],
            fail_examples=["'Scout' — common word, definitely taken"],
        ),
        Criterion(
            id="name_variety",
            category="range",
            description="Names span different naming strategies — not all the same pattern",
            pass_condition="Mix of approaches: metaphorical, coined, real-word-repurposed, "
                          "compound, classical/Latin root. At least 3 different strategies.",
            scoring=_weighted(6, [
                ("strategy_diversity", "At least 3 different naming strategies used", 0.50,
                 "1.0 if 4+ strategies, 0.75 if 3, 0.5 if 2, 0.0 if all same"),
                ("range_of_tone", "Mix of serious/approachable/bold", 0.50,
                 "1.0 if clear tonal range, 0.5 if some variation, 0.0 if monotone"),
            ]),
            pass_examples=["Metaphorical (Redline) + coined (Clausefy) + classical (Lex Machina) + compound (Inkwell)"],
            fail_examples=["5 variations of '[Legal word] + AI'"],
        ),
    ]

    return Rubric(
        task=task,
        domain="creative_naming",
        criteria=criteria,
        total_points=sum(c.scoring.max_points for c in criteria),
        pass_threshold=0.75,
    )


# ============================================================================
# Task 9: Bash Script — PostgreSQL Backup to S3
# ============================================================================

def build_bash_backup_rubric() -> Rubric:
    task = "Write a bash script that backs up a PostgreSQL database to S3 with rotation, logging, and error notifications"

    criteria = [
        Criterion(
            id="bash_correctness",
            category="functionality",
            description="Script performs correct pg_dump → compress → upload → rotate pipeline",
            pass_condition="Uses pg_dump with appropriate flags. Compresses output (gzip/zstd). "
                          "Uploads to S3 with aws cli. Rotates old backups by age or count.",
            scoring=_weighted(12, [
                ("dump_command", "pg_dump with correct flags (--format, --no-owner, etc.)", 0.30,
                 "1.0 if pg_dump with appropriate format flags, 0.5 if basic, 0.0 if wrong"),
                ("compression", "Output compressed before upload", 0.20,
                 "1.0 if compressed (gzip/zstd), 0.0 if raw SQL upload"),
                ("s3_upload", "aws s3 cp/sync with correct path and options", 0.25,
                 "1.0 if correct aws s3 cp with proper path, 0.0 if wrong"),
                ("rotation", "Deletes backups older than N days or keeps last N", 0.25,
                 "1.0 if implemented correctly, 0.5 if partially, 0.0 if missing"),
            ]),
            pass_examples=["pg_dump -Fc | gzip > backup.gz && aws s3 cp ... && find/delete old"],
            fail_examples=["pg_dump with no compression, no rotation logic"],
        ),
        Criterion(
            id="bash_safety",
            category="reliability",
            description="Script is safe — set -euo pipefail, no secrets in code, cleanup on failure",
            pass_condition="set -euo pipefail. Trap for cleanup. No hardcoded passwords. "
                          "Uses .pgpass or env vars. Temp files cleaned up.",
            scoring=_penalty(10, {
                "no_set_e": -2.0,
                "no_pipefail": -1.5,
                "hardcoded_password": -3.0,
                "no_trap_cleanup": -1.5,
                "no_temp_file_cleanup": -1.0,
                "unquoted_variables": -1.0,
                "no_lockfile": -0.5,
            }),
            pass_examples=["set -euo pipefail, trap cleanup EXIT, reads creds from env"],
            fail_examples=["No error handling, password in script, temp files left behind"],
        ),
        Criterion(
            id="bash_logging",
            category="observability",
            description="Comprehensive logging with timestamps and log levels",
            pass_condition="Timestamped log function. Logs start/success/failure/rotation. "
                          "Writes to file AND stdout. Includes backup size and duration.",
            scoring=_weighted(8, [
                ("log_function", "Dedicated log function with timestamps", 0.30,
                 "1.0 if log() function with ISO timestamps, 0.5 if echo with date, 0.0 if plain echo"),
                ("log_completeness", "Logs all key events (start, size, duration, rotate, done)", 0.35,
                 "% of key events logged"),
                ("log_destination", "Writes to both file and stdout", 0.35,
                 "1.0 if tee to file + stdout, 0.5 if one, 0.0 if neither"),
            ]),
            pass_examples=["log() { echo \"[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [$1] $2\" | tee -a $LOG; }"],
            fail_examples=["Random echo statements with no timestamps"],
        ),
        Criterion(
            id="bash_notifications",
            category="alerting",
            description="Error notifications via practical channel (email, Slack, PagerDuty)",
            pass_condition="On failure: sends notification with error details and context. "
                          "Configurable notification channel. Includes backup name, error message, timestamp.",
            scoring=_weighted(8, [
                ("notification_impl", "Actually sends notification on failure", 0.40,
                 "1.0 if implemented (curl to Slack, mail, etc.), 0.0 if TODO/placeholder"),
                ("error_context", "Notification includes useful context (timestamp, db, error)", 0.35,
                 "1.0 if rich context, 0.5 if basic, 0.0 if just 'backup failed'"),
                ("configurability", "Channel/endpoint configurable via env var", 0.25,
                 "1.0 if configurable, 0.5 if hardcoded but works, 0.0 if neither"),
            ]),
            pass_examples=["Slack webhook with formatted message including db name, error, and log tail"],
            fail_examples=["# TODO: add notifications"],
        ),
        Criterion(
            id="bash_configurability",
            category="usability",
            description="Script is configurable via environment variables with sensible defaults",
            pass_condition="Key params via env vars: DB_NAME, S3_BUCKET, RETENTION_DAYS, etc. "
                          "Defaults provided. Usage/help flag. Validates required vars.",
            scoring=_weighted(6, [
                ("env_var_config", "Key params from env vars with defaults", 0.40,
                 "% of configurable params using env vars with fallback defaults"),
                ("validation", "Validates required vars exist before starting", 0.30,
                 "1.0 if checks all required vars, 0.5 if some, 0.0 if none"),
                ("help_flag", "--help flag with usage instructions", 0.30,
                 "1.0 if --help works, 0.0 if no help"),
            ]),
            pass_examples=["DB_NAME=${DB_NAME:?'DB_NAME required'}, RETENTION=${RETENTION_DAYS:-30}"],
            fail_examples=["Hardcoded db name, bucket, and retention in script body"],
        ),
    ]

    return Rubric(
        task=task,
        domain="bash_scripting",
        criteria=criteria,
        total_points=sum(c.scoring.max_points for c in criteria),
        pass_threshold=0.85,
    )


# ============================================================================
# Task 10: 1-Page Investment Memo — Defense Drone Series A
# ============================================================================

def build_investment_memo_rubric() -> Rubric:
    task = "Draft a 1-page investment memo on a hypothetical Series A company in the defense drone space"

    criteria = [
        Criterion(
            id="memo_structure",
            category="format",
            description="Follows standard 1-page memo format with all required sections",
            pass_condition="Sections: Company Overview, Market Opportunity, Product/Technology, "
                          "Team, Traction, Deal Terms, Key Risks, Recommendation. "
                          "Fits on one page (~500-700 words).",
            scoring=_weighted(10, [
                ("section_coverage", "All required sections present", 0.35,
                 "% of required sections (overview, market, product, team, traction, terms, risks, rec)"),
                ("page_constraint", "Fits on one page (500-700 words)", 0.30,
                 "1.0 if 500-700 words, 0.7 if 700-850, 0.3 if 400-500, 0.0 if >900"),
                ("scannable_format", "Headers, bullets within sections, dense but readable", 0.35,
                 "1.0 if scannable with clear visual hierarchy, 0.0 if wall of text"),
            ]),
            pass_examples=["8 sections, 650 words, each section 2-4 bullet points"],
            fail_examples=["3-page narrative essay, or 200-word skim"],
        ),
        Criterion(
            id="memo_market",
            category="analysis",
            description="Market opportunity is sized and specific to defense drones, not generic TAM",
            pass_condition="SAM/SOM, not just TAM. Specific to defense drone segment. "
                          "Cites or constructs credible numbers. Identifies tailwinds "
                          "(DoD budget trends, Ukraine lessons, NDAA provisions).",
            scoring=_weighted(10, [
                ("market_specificity", "Defense drone SAM, not generic 'drone market'", 0.35,
                 "1.0 if defense-specific SAM/SOM, 0.5 if TAM only, 0.0 if generic"),
                ("credible_sizing", "Numbers are plausible with cited or constructed basis", 0.30,
                 "1.0 if sourced/constructed, 0.5 if asserted, 0.0 if absent"),
                ("tailwind_identification", "Specific policy/geopolitical tailwinds cited", 0.35,
                 "% of relevant tailwinds identified (DoD budget, NDAA, Ukraine, Replicator)"),
            ]),
            pass_examples=["'Defense sUAS SAM: $8B by 2028 (up from $3B), driven by DoD Replicator initiative and FY26 NDAA line items'"],
            fail_examples=["'The global drone market is expected to reach $50B by 2030'"],
        ),
        Criterion(
            id="memo_thesis",
            category="conviction",
            description="Investment thesis is crisp — clear 'why this company, why now'",
            pass_condition="2-3 sentence thesis that answers: What's the insight? "
                          "Why is this team positioned? What's the timing catalyst? "
                          "Must be specific enough that it couldn't apply to any defense startup.",
            scoring=_weighted(10, [
                ("insight_clarity", "Core insight is specific and non-obvious", 0.40,
                 "1.0 if specific insight, 0.5 if generic but directionally right, 0.0 if boilerplate"),
                ("team_match", "Why this team specifically is positioned to win", 0.30,
                 "1.0 if specific team-market fit, 0.5 if generic team praise, 0.0 if absent"),
                ("timing_catalyst", "Clear 'why now' with specific catalyst", 0.30,
                 "1.0 if specific timing argument, 0.5 if vague, 0.0 if absent"),
            ]),
            pass_examples=["'DoD is shifting from $50M primes-built systems to $500K attritable drones — [Company] has the only NDAA-compliant autonomy stack that integrates with existing C2 systems, built by ex-Anduril engineers who shipped the first production Altius system.'"],
            fail_examples=["'Defense is a big market and drones are the future.'"],
        ),
        Criterion(
            id="memo_risks",
            category="diligence",
            description="Key risks are honest, specific, and include mitigants",
            pass_condition="3-5 real risks (not strawmen). At least one each: market risk, "
                          "execution risk, regulatory/ITAR risk. Each has a mitigant or monitoring plan.",
            scoring=_weighted(8, [
                ("risk_quality", "Risks are real and specific, not generic", 0.40,
                 "% of risks that are specific to this company/market"),
                ("risk_coverage", "Market, execution, and regulatory/ITAR risks all addressed", 0.30,
                 "1.0 if all 3 categories, 0.5 if 2, 0.0 if 1"),
                ("mitigants", "Each risk has a plausible mitigant or monitoring plan", 0.30,
                 "% of risks with stated mitigants"),
            ]),
            pass_examples=["'ITAR compliance burden limits sales velocity — mitigant: CTO has existing DSP-5/DSP-73 experience from Lockheed tenure'"],
            fail_examples=["'Risk: competition. Risk: market might not grow.'"],
        ),
        Criterion(
            id="memo_deal_terms",
            category="practicality",
            description="Deal terms are realistic and internally consistent",
            pass_condition="Pre-money valuation, round size, lead investor type, and use of funds. "
                          "Values are stage-appropriate (Series A defense: $15-40M pre). "
                          "Use of funds is specific (hiring, ITAR facility, production line).",
            scoring=_weighted(6, [
                ("completeness", "Valuation, round size, ownership target stated", 0.40,
                 "% of deal terms present"),
                ("stage_appropriateness", "Values are realistic for Series A defense startup", 0.30,
                 "1.0 if realistic, 0.5 if slightly off, 0.0 if unrealistic"),
                ("use_of_funds", "Specific allocation of capital", 0.30,
                 "1.0 if specific breakdown, 0.5 if vague, 0.0 if absent"),
            ]),
            pass_examples=["'$20M Series A at $60M pre. Use: 40% eng/autonomy, 25% ITAR facility, 20% BD, 15% ops'"],
            fail_examples=["'Raising a Series A at a good valuation'"],
        ),
    ]

    return Rubric(
        task=task,
        domain="investment_memo",
        criteria=criteria,
        total_points=sum(c.scoring.max_points for c in criteria),
        pass_threshold=0.85,
    )


# ============================================================================
# Registry
# ============================================================================

ALL_SAMPLE_RUBRICS = [
    build_cold_outreach_email_rubric,       # 1
    build_csv_parser_rubric,                # 2
    build_exec_summary_rubric,              # 3
    build_sql_ltv_rubric,                   # 4
    build_counterargument_rubric,           # 5
    build_billing_schema_rubric,            # 6
    build_explanation_rubric,               # 7
    build_naming_rubric,                    # 8
    build_bash_backup_rubric,               # 9
    build_investment_memo_rubric,           # 10
]

SAMPLE_TASKS = {
    "cold_outreach_email": build_cold_outreach_email_rubric,
    "csv_parser": build_csv_parser_rubric,
    "exec_summary": build_exec_summary_rubric,
    "sql_ltv_query": build_sql_ltv_rubric,
    "agi_counterargument": build_counterargument_rubric,
    "billing_schema": build_billing_schema_rubric,
    "attention_explanation": build_explanation_rubric,
    "startup_naming": build_naming_rubric,
    "bash_backup": build_bash_backup_rubric,
    "investment_memo": build_investment_memo_rubric,
}


def build_rubric_for_task(task_number: int) -> Rubric:
    """Build a sample rubric by task number (1-10)."""
    if not 1 <= task_number <= 10:
        raise ValueError(f"Task number must be 1-10, got {task_number}")
    return ALL_SAMPLE_RUBRICS[task_number - 1]()


# ============================================================================
# CLI — Print summary of all sample rubrics
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("SAMPLE RUBRICS — 10 Task-Specific Evaluation Systems")
    print("=" * 80)

    for i, builder in enumerate(ALL_SAMPLE_RUBRICS, 1):
        rubric = builder()
        print(f"\n{'─' * 70}")
        print(f"  Task {i}: {rubric.task[:65]}")
        print(f"  Domain: {rubric.domain} | Criteria: {len(rubric.criteria)} | "
              f"Max Points: {rubric.total_points} | Pass: {rubric.pass_threshold:.0%}")
        print(f"{'─' * 70}")

        for c in rubric.criteria:
            method = c.scoring.method.value
            pts = c.scoring.max_points
            n_sub = len(c.scoring.sub_attributes)
            n_pen = len(c.scoring.penalties)
            detail = f"{n_sub} subs" if n_sub else f"{n_pen} penalties" if n_pen else "binary"
            print(f"    {c.id:25s} | {c.category:20s} | {method:20s} | {pts:2d}pts | {detail}")

    print(f"\n{'=' * 80}")
    total_criteria = sum(len(builder().criteria) for builder in ALL_SAMPLE_RUBRICS)
    total_points = sum(builder().total_points for builder in ALL_SAMPLE_RUBRICS)
    print(f"TOTALS: {total_criteria} criteria across 10 rubrics, {total_points} max points")
    print(f"{'=' * 80}")
