#!/usr/bin/env python3
"""Test preamble stripping logic."""
import re
import sys
sys.path.insert(0, ".")

# Import the actual class
from rubric_harness import GenerationAgent

strip = GenerationAgent._strip_preamble

# Test 1: The actual cold_outreach_email preamble
t1 = (
    "Now I'll apply the specific fixes identified by the evaluator "
    "to improve the failing criteria while preserving the sections "
    "that are already scoring well:\n\n"
    "**Subject:** Angel check for Lio\n\nVladimir,"
)
r1 = strip(t1)
assert r1.startswith("**Subject:**"), f"FAIL 1: {r1[:60]}"
print("Test 1 PASS: cold_outreach preamble stripped")

# Test 2: Multi-sentence "Based on..."
t2 = (
    "Based on the feedback, I need to fix several issues. "
    "The current draft is incomplete.\n\n"
    "```json\n{}\n```"
)
r2 = strip(t2)
assert r2.startswith("```json"), f"FAIL 2: {r2[:60]}"
print("Test 2 PASS: Based on... stripped")

# Test 3: Multiple meta paragraphs
t3 = (
    "I need to search for a real company.\n\n"
    "Based on the feedback, I need to make edits.\n\n"
    "**Subject:** Quick question"
)
r3 = strip(t3)
assert r3.startswith("**Subject:**"), f"FAIL 3: {r3[:60]}"
print("Test 3 PASS: multiple preamble paragraphs stripped")

# Test 4: Clean content — no modification
t4 = "**Subject:** Angel check\n\nHi Vladimir,"
r4 = strip(t4)
assert r4 == t4
print("Test 4 PASS: clean content unchanged")

# Test 5: Script with preamble
t5 = (
    "Looking at the feedback, the script already has all "
    "the required features:\n\n"
    "#!/bin/bash\nset -euo pipefail\necho done"
)
r5 = strip(t5)
assert r5.startswith("#!/bin/bash"), f"FAIL 5: {r5[:60]}"
print("Test 5 PASS: script preamble stripped")

# Test 6: No blank line = don't strip (safety)
t6 = (
    "Based on the feedback, here is the improved version:\n"
    "# Investment Memo\nCompany: Acme Corp lots of content here " * 5
)
r6 = strip(t6)
assert r6 == t6.lstrip(), f"FAIL 6: stripped without blank line"
print("Test 6 PASS: no blank line = no strip")

# Test 7: 30% safety check — don't strip if result too short
t7 = "I need to do something.\n\nOK"
r7 = strip(t7)
assert r7 == t7.lstrip(), f"FAIL 7: safety check failed"
print("Test 7 PASS: 30% safety check")

# Test 8: "Let me search..." preamble
t8 = (
    "Let me search for more specific information about a recent "
    "Series A company to make this email more realistic.\n\n"
    "**Subject:** Congrats on the round\n\nHi Sarah,"
)
r8 = strip(t8)
assert r8.startswith("**Subject:**"), f"FAIL 8: {r8[:60]}"
print("Test 8 PASS: 'Let me...' stripped")

# Test 9: "However, since..." preamble
t9 = (
    "However, since I'm instructed to follow the structured feedback "
    "precisely, I'll need to enhance the nuance even further.\n\n"
    "The argument against AGI by 2030 rests on three pillars."
)
r9 = strip(t9)
assert r9.startswith("The argument"), f"FAIL 9: {r9[:60]}"
print("Test 9 PASS: 'However, since...' stripped")

# Test 10: "I will now..." preamble
t10 = (
    "I will now make targeted improvements to address the failing "
    "criteria identified in the evaluation.\n\n"
    "# Executive Summary\n\nThe market for AI-driven procurement..."
)
r10 = strip(t10)
assert r10.startswith("# Executive Summary"), f"FAIL 10: {r10[:60]}"
print("Test 10 PASS: 'I will now...' stripped")

print("\nAll tests passed!")
