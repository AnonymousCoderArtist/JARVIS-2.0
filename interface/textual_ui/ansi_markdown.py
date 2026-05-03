from __future__ import annotations

from typing import TYPE_CHECKING

import re
from pygments.token import Token
from textual.content import Content
from textual.highlight import HighlightTheme, highlight
from textual.widgets import Markdown
from textual.widgets._markdown import MarkdownFence


class AnsiHighlightTheme(HighlightTheme):
    STYLES = {
        Token.Comment: "ansi_bright_black italic",
        Token.Error: "ansi_red",
        Token.Generic.Strong: "bold",
        Token.Generic.Emph: "italic",
        Token.Generic.Error: "ansi_red",
        Token.Generic.Heading: "ansi_blue underline",
        Token.Generic.Subheading: "ansi_blue",
        Token.Keyword: "ansi_magenta",
        Token.Keyword.Constant: "ansi_cyan",
        Token.Keyword.Namespace: "ansi_magenta",
        Token.Keyword.Type: "ansi_cyan",
        Token.Literal.Number: "ansi_yellow",
        Token.Literal.String.Backtick: "ansi_bright_black",
        Token.Literal.String: "ansi_green",
        Token.Literal.String.Doc: "ansi_green italic",
        Token.Literal.String.Double: "ansi_green",
        Token.Name: "ansi_default",
        Token.Name.Attribute: "ansi_yellow",
        Token.Name.Builtin: "ansi_cyan",
        Token.Name.Builtin.Pseudo: "italic",
        Token.Name.Class: "ansi_yellow",
        Token.Name.Constant: "ansi_red",
        Token.Name.Decorator: "ansi_blue",
        Token.Name.Function: "ansi_blue",
        Token.Name.Function.Magic: "ansi_blue",
        Token.Name.Tag: "ansi_blue",
        Token.Name.Variable: "ansi_default",
        Token.Number: "ansi_yellow",
        Token.Operator: "ansi_default",
        Token.Operator.Word: "ansi_magenta",
        Token.String: "ansi_green",
        Token.Whitespace: "",
    }


class AnsiMarkdownFence(MarkdownFence):
    @classmethod
    def highlight(cls, code: str, language: str, ansi: bool = False, dark: bool = False) -> Content:
        return highlight(code, language=language or None, theme=AnsiHighlightTheme)


# Regex patterns for LaTeX/math detection
# Block math: $$...$$ (multi-line with optional newlines)
_BLOCK_MATH_RE = re.compile(r'\$\$([\s\S]+?)\$\$', re.MULTILINE)
# Inline math: $...$ (single line, no newlines inside)
_INLINE_MATH_RE = re.compile(r'\$([^$\n]+)\$')


def detect_math_blocks(text: str) -> list[tuple[str, bool, int, int]]:
    """Detect LaTeX/math blocks in text.

    Returns list of (math_content, is_block, start_pos, end_pos) tuples.
    Results are sorted by start position.

    Example:
        >>> detect_math_blocks("Solve $x=1$ and $$\\int x$$")
        [("x=1", False, 6, 11), ("\\int x", True, 15, 25)]
    """
    results = []
    seen_starts: set[int] = set()

    # Block math ($$...$$)
    for match in _BLOCK_MATH_RE.finditer(text):
        if match.start() not in seen_starts:
            results.append((match.group(1).strip(), True, match.start(), match.end()))
            seen_starts.add(match.start())

    # Inline math ($...$) - skip if it overlaps with block math positions
    for match in _INLINE_MATH_RE.finditer(text):
        # Check if this inline match is inside any block match
        is_inside_block = False
        for block_content, is_block, start, end in results:
            if is_block and start < match.start() < end:
                is_inside_block = True
                break

        if not is_inside_block and match.start() not in seen_starts:
            results.append((match.group(1).strip(), False, match.start(), match.end()))
            seen_starts.add(match.start())

    # Sort by start position
    results.sort(key=lambda x: x[2])
    return results


class AnsiMarkdown(Markdown):
    BLOCKS = {
        **Markdown.BLOCKS,
        "fence": AnsiMarkdownFence,
        "code_block": AnsiMarkdownFence,
    }