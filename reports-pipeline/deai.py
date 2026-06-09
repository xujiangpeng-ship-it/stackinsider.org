#!/usr/bin/env python3
"""
deai.py — 6-step anti-AI post-processing engine.

Applies transformations to raw LLM output to eliminate detectable
AI-generated patterns: paragraph restructuring, transition variation,
sentence length diversification, opening rotation, conclusion cutting,
and human-trace injection.

Input: Markdown text (stdin or file)
Output: DeAI-processed Markdown text (stdout or file)

Author: stackinsider.org pipeline
"""

import argparse
import logging
import random
import re
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("deai")

# ---------------------------------------------------------------------------
# Step 1: Paragraph Split & Merge — break AI's predictable paragraph rhythm
# ---------------------------------------------------------------------------

def step1_paragraph_split_merge(text: str) -> str:
    """
    AI tends to produce uniform paragraph lengths (3-5 sentences each).
    We intentionally break this pattern: short paras get merged, long ones split.
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    result = []
    i = 0

    while i < len(paragraphs):
        para = paragraphs[i]
        sentences = re.split(r"(?<=[.!?])\s+", para)

        if len(sentences) >= 8:
            # Long paragraph — split in half
            mid = len(sentences) // 2
            result.append(" ".join(sentences[:mid]))
            result.append(" ".join(sentences[mid:]))
        elif len(sentences) <= 2 and i + 1 < len(paragraphs):
            # Short paragraph — merge with next
            merged = para + " " + paragraphs[i + 1]
            result.append(merged)
            i += 1
        else:
            result.append(para)

        i += 1

    return "\n\n".join(result)


# ---------------------------------------------------------------------------
# Step 2: Transition Word Variation — 15 groups to avoid repetition
# ---------------------------------------------------------------------------

TRANSITION_GROUPS = {
    "addition": [
        "What's more,", "Beyond that,", "On top of this,", "Adding to this,",
        "Not to mention,", "Coupled with this,", "Alongside that,", "Plus,",
        "Additionally,", "Furthermore,", "Moreover,", "Also worth noting:",
        "And here's the kicker:", "Building on that,", "Taking it a step further,",
    ],
    "contrast": [
        "That said,", "Flip side:", "But here's the thing:", "Then again,",
        "Yet,", "Even so,", "Still,", "On the other hand,",
        "The counterpoint:", "Where this gets tricky:", "Not so fast:",
        "The catch is,", "Here's the rub:", "Where things get complicated:",
        "But dig deeper and,",
    ],
    "causation": [
        "Here's why:", "The upshot:", "Bottom line:", "This boils down to:",
        "The underlying driver:", "What's fueling this:", "Trace it back and,",
        "The reason is straightforward:", "This stems from:", "The root cause:",
        "It comes down to this:", "The catalyst here:", "Driving this shift:",
        "What's behind the numbers:", "The force at play:",
    ],
    "example": [
        "Case in point:", "Take this example:", "Consider this:",
        "Here's a real one:", "To put that in perspective:", "Picture this:",
        "A concrete example:", "This played out recently when:",
        "Seen in practice:", "Here's how it actually looks:",
        "Real-world illustration:", "Just look at:",
        "The pattern is clear in:", "For instance,", "A textbook case:",
    ],
    "conclusion": [
        "Where this leaves us:", "The takeaway:", "What it all means:",
        "Summing it up:", "In a nutshell:", "The net effect:",
        "If you take one thing away:", "The long and short of it:",
        "Here's where we land:", "So what's the verdict?",
        "Pulling it together:", "The signal through the noise:",
        "At the end of the day,", "What should you do with this?",
        "The practical upshot:",
    ],
}

def step2_transition_variation(text: str) -> str:
    """
    Replace common AI transition phrases with varied alternatives.
    Each transition group gets a random pick, cycling through the group.
    """
    common_transitions = {
        "Additionally,": "addition",
        "Furthermore,": "addition",
        "Moreover,": "addition",
        "In addition,": "addition",
        "However,": "contrast",
        "Nevertheless,": "contrast",
        "On the other hand,": "contrast",
        "Therefore,": "causation",
        "Consequently,": "causation",
        "As a result,": "causation",
        "For example,": "example",
        "For instance,": "example",
        "In conclusion,": "conclusion",
        "To summarize,": "conclusion",
        "Overall,": "conclusion",
    }

    used = {g: list(t) for g, t in TRANSITION_GROUPS.items()}

    def replace_match(match):
        word = match.group(0)
        group = common_transitions.get(word)
        if group and used[group]:
            replacement = used[group].pop(0)
            used[group].append(replacement)
            return replacement
        return word

    pattern = re.compile(
        r"\b(?:" + "|".join(re.escape(k) for k in common_transitions) + r")\b"
    )
    return pattern.sub(replace_match, text)


# ---------------------------------------------------------------------------
# Step 3: Sentence Length Diversification
# ---------------------------------------------------------------------------

def step3_sentence_length_variation(text: str) -> str:
    """
    AI produces uniform sentence lengths (15-25 words).
    We break sentences to create short (2-5 words), medium, and long variety.
    """
    sentences = re.split(r"(?<=[.!?])\s+", text)
    result = []

    for s in sentences:
        words = s.split()
        if len(words) > 35:
            # Very long sentence — break at natural comma points
            parts = re.split(r",\s+", s)
            if len(parts) >= 3:
                mid = len(parts) // 2
                result.append(", ".join(parts[:mid]) + ".")
                result.append(", ".join(parts[mid:]))
            else:
                # Break roughly in half by words
                mid = len(words) // 2
                result.append(" ".join(words[:mid]) + ".")
                result.append(" ".join(words[mid:]))
        else:
            result.append(s)

    return " ".join(result)


# ---------------------------------------------------------------------------
# Step 4: Opening Sentence Rotation — avoid "In today's..." pattern
# ---------------------------------------------------------------------------

AI_OPENERS = [
    r"^In today'?s\s+(?:fast-paced\s+)?(?:digital\s+)?(?:business\s+)?landscape",
    r"^In the (?:ever-evolving|rapidly changing) world of",
    r"^As (?:we|businesses) (?:navigate|move through|enter)",
    r"^The (?:modern|current) (?:business|technology) landscape",
    r"^It is (?:widely|commonly) (?:recognized|acknowledged|understood) that",
]

def step4_opening_rotation(text: str) -> str:
    """
    Strip or rephrase AI-cliche opening sentences.
    """
    for pattern in AI_OPENERS:
        text = re.sub(pattern + r"[^.]*\.\s*", "", text, count=1)

    return text.strip()


# ---------------------------------------------------------------------------
# Step 5: Conclusion Verbal Tic Cutting
# ---------------------------------------------------------------------------

AI_CONCLUSIONS = [
    r"In conclusion,.*?(?=\n\n|\Z)",
    r"Ultimately,.*?(?=\n\n|\Z)",
    r"As we have seen,.*?(?=\n\n|\Z)",
    r"It is clear that.*?(?=\n\n|\Z)",
    r"Without a doubt,.*?(?=\n\n|\Z)",
]

def step5_conclusion_cutting(text: str) -> str:
    """
    Remove formulaic AI conclusion paragraphs.
    """
    for pattern in AI_CONCLUSIONS:
        text = re.sub(pattern, "", text, flags=re.DOTALL | re.IGNORECASE)
    return text.strip()


# ---------------------------------------------------------------------------
# Step 6: Human Trace Injection
# ---------------------------------------------------------------------------

HUMAN_TRACES = [
    "Honestly,", "If I'm being blunt,", "Look,", "Here's the thing:",
    "I'll say it:", "The truth is,", "Let's be real:", "Real talk:",
    "Here's what nobody's saying:", "The quiet part out loud:",
    "Put simply:", "Cut through the noise:", "The data, stripped bare:",
    "No sugar-coating:", "Here's what the numbers actually say:",
    "I've seen this pattern before:", "This is where it gets interesting:",
    "The part most analyses miss:", "Here's the nuance that matters:",
    "And this is key:", "The detail worth pausing on:",
]

def step6_human_trace_injection(text: str) -> str:
    """
    Inject human-like conversational traces at natural break points.
    Adds 2-4 traces at paragraph starts, avoiding overuse.
    """
    paragraphs = text.split("\n\n")
    if len(paragraphs) <= 3:
        return text

    # Skip headers (#, ##, ###, |, >) and code blocks
    injectable_indices = [
        i for i, p in enumerate(paragraphs)
        if p.strip() and not p.strip().startswith(("#", "|", ">", "*", "-", "```"))
    ]

    num_traces = min(random.randint(2, 4), len(injectable_indices))
    selected = random.sample(injectable_indices, num_traces)

    for idx in selected:
        trace = random.choice(HUMAN_TRACES)
        paragraphs[idx] = trace + " " + paragraphs[idx]

    return "\n\n".join(paragraphs)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def deai_pipeline(text: str) -> str:
    """Execute all 6 de-AI steps in sequence."""
    logger.info("Step 1: Paragraph split/merge")
    text = step1_paragraph_split_merge(text)

    logger.info("Step 2: Transition word variation")
    text = step2_transition_variation(text)

    logger.info("Step 3: Sentence length diversification")
    text = step3_sentence_length_variation(text)

    logger.info("Step 4: Opening sentence rotation")
    text = step4_opening_rotation(text)

    logger.info("Step 5: Conclusion verbal tic cutting")
    text = step5_conclusion_cutting(text)

    logger.info("Step 6: Human trace injection")
    text = step6_human_trace_injection(text)

    return text


def main():
    parser = argparse.ArgumentParser(description="deai.py — 6-step anti-AI post-processing")
    parser.add_argument("input", nargs="?", help="Input file path (default: stdin)")
    parser.add_argument("-o", "--output", help="Output file path (default: stdout)")
    args = parser.parse_args()

    if args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            text = f.read()
    else:
        text = sys.stdin.read()

    result = deai_pipeline(text)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result)
        logger.info(f"Output written to {args.output}")
    else:
        print(result)


if __name__ == "__main__":
    main()