"""Lightweight Unicode-based math rendering for terminal.

This module provides simple LaTeX-to-Unicode rendering for common mathematical
expressions. It's completely offline, uses minimal RAM, and won't break anything.
"""

from __future__ import annotations

import asyncio
import re

# Superscripts
_SUPERSCRIPTS = {
    "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
    "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
    "n": "ⁿ", "i": "ⁱ", "+": "⁺", "-": "⁻", "=": "⁼",
    "a": "ᵃ", "b": "ᵇ", "d": "ᵈ", "e": "ᵉ", "h": "ʰ",
    "x": "ˣ", "y": "ʸ",
}

# Subscripts
_SUBSCRIPTS = {
    "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄",
    "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉",
    "a": "ₐ", "e": "ₑ", "h": "ₕ", "i": "ᵢ", "j": "ⱼ",
    "k": "ₖ", "l": "ₗ", "m": "ₘ", "n": "ₙ", "o": "ₒ",
    "p": "ₚ", "r": "ᵣ", "s": "ₛ", "t": "ₜ", "u": "ᵤ",
    "v": "ᵥ", "x": "ₓ",
}

# Simple fractions
_FRACTIONS = {
    "1/2": "½", "1/3": "⅓", "2/3": "⅔",
    "1/4": "¼", "3/4": "¾", "1/5": "⅕", "2/5": "⅖",
    "3/5": "⅗", "4/5": "⅘", "1/6": "⅙", "5/6": "⅚",
}

# All math symbols - order matters for some
_MATH_SYMBOLS = [
    (r"\cdot", "·"), (r"\times", "×"), (r"\div", "÷"),
    (r"\pm", "±"), (r"\mp", "∓"), (r"\ast", "∗"),
    (r"\star", "⋆"), (r"\circ", "°"), (r"\bullet", "•"),
    (r"\oplus", "⊕"), (r"\ominus", "⊖"), (r"\otimes", "⊗"),
    (r"\oslash", "⊘"), (r"\odot", "⊙"),
    (r"\leq", "≤"), (r"\geq", "≥"), (r"\neq", "≠"),
    (r"\approx", "≈"), (r"\equiv", "≡"), (r"\sim", "∼"),
    (r"\simeq", "≃"), (r"\cong", "≅"), (r"\perp", "⊥"),
    (r"\parallel", "∥"), (r"\propto", "∝"),
    (r"\in", "∈"), (r"\notin", "∉"), (r"\subset", "⊂"),
    (r"\supset", "⊃"), (r"\cup", "∪"), (r"\cap", "∩"),
    (r"\emptyset", "∅"), (r"\varnothing", "∅"),
    (r"\forall", "∀"), (r"\exists", "∃"), (r"\nexists", "∄"),
    (r"\land", "∧"), (r"\lor", "∨"), (r"\lnot", "¬"),
    (r"\neg", "¬"), (r"\implies", "⇒"), (r"\impliedby", "⇐"),
    (r"\iff", "⇔"),
    (r"\alpha", "α"), (r"\beta", "β"), (r"\gamma", "γ"),
    (r"\delta", "δ"), (r"\epsilon", "ε"), (r"\zeta", "ζ"),
    (r"\eta", "η"), (r"\theta", "θ"), (r"\iota", "ι"),
    (r"\kappa", "κ"), (r"\lambda", "λ"), (r"\mu", "μ"),
    (r"\nu", "ν"), (r"\xi", "ξ"), (r"\pi", "π"),
    (r"\rho", "ρ"), (r"\sigma", "σ"), (r"\tau", "τ"),
    (r"\upsilon", "υ"), (r"\phi", "φ"), (r"\chi", "χ"),
    (r"\psi", "ψ"), (r"\omega", "ω"),
    (r"\partial", "∂"), (r"\nabla", "∇"), (r"\sum", "∑"),
    (r"\prod", "∏"), (r"\int", "∫"), (r"\lim", "lim"),
    (r"\infty", "∞"), (r"\sin", "sin"), (r"\cos", "cos"),
    (r"\tan", "tan"), (r"\arcsin", "arcsin"), (r"\arccos", "arccos"),
    (r"\arctan", "arctan"), (r"\ln", "ln"), (r"\log", "log"),
    (r"\exp", "exp"), (r"\langle", "⟨"), (r"\rangle", "⟩"),
    (r"\lceil", "⌈"), (r"\rceil", "⌉"), (r"\lfloor", "⌊"),
    (r"\rfloor", "⌋"), (r"\to", "→"), (r"\rightarrow", "→"),
    (r"\leftarrow", "←"), (r"\Rightarrow", "⇒"), (r"\Leftarrow", "⇐"),
    (r"\cdots", "⋯"), (r"\ldots", "…"), (r"\vdots", "⋮"),
    (r"\ddots", "⋱"), (r"\prime", "′"), (r"\degree", "°"),
    (r"\angle", "∠"), (r"\triangle", "△"), (r"\square", "□"),
]


def _to_superscript(text):
    return "".join(_SUPERSCRIPTS.get(c, c) for c in text)


def _to_subscript(text):
    return "".join(_SUBSCRIPTS.get(c, c) for c in text)


def _replace_symbols(text):
    result = text
    for frac, uni in _FRACTIONS.items():
        result = result.replace(frac, uni)
    for sp, su in _SUPERSCRIPTS.items():
        result = result.replace("^" + sp, su)
    result = result.replace("^", "⁽")
    for sb, su in _SUBSCRIPTS.items():
        result = result.replace("_" + sb, su)
    result = result.replace("_", "₽")
    for latex, uni in _MATH_SYMBOLS:
        result = result.replace(latex, uni)
    return result


def render_math_inline(text):
    text = text.strip()
    # Handle frac{...}{...}
    text = re.sub(r"\\frac\{([^}]+)\}\{([^}]+)\}", r"(\1/\2)", text)
    # Remove command prefixes
    for cmd in ["frac", "sqrt", "text", "mathrm", "boxed", "left", "right"]:
        text = text.replace("\\" + cmd, "")
    # Superscripts
    text = re.sub(r"\^\{(\w+)\}", lambda m: _to_superscript(m.group(1)), text)
    text = re.sub(r"\^(\w)", lambda m: _to_superscript(m.group(1)), text)
    # Subscripts
    text = re.sub(r"_\{(\w+)\}", lambda m: _to_subscript(m.group(1)), text)
    # Clean braces
    text = text.replace("{", "").replace("}", "")
    return _replace_symbols(text)


def render_math_block(text):
    lines = text.strip().split("\n")
    return "\n".join(render_math_inline(line) for line in lines)


def render_latex(text):
    from interface.textual_ui.ansi_markdown import detect_math_blocks
    blocks = detect_math_blocks(text)
    if not blocks:
        return text
    result, last = [],0
    for content, is_block, start, end in blocks:
        result.append(text[last:start])
        math = render_math_block(content) if is_block else render_math_inline(content)
        result.append(f"⟦{math}⟧")
        last = end
    result.append(text[last:])
    return "".join(result)


def render_inline(text):
    return render_math_inline(text)


def render_block(text):
    return render_math_block(text)


# ---------------------------------------------------------------------------
# Streaming (real-time) renderers
# ---------------------------------------------------------------------------

async def render_math_inline_stream(text):
    """Async generator that yields rendered inline math as a single chunk.
    
    For true character-by-character streaming, replace the yield with a loop
    over `rendered` characters.
    """
    rendered = await asyncio.get_event_loop().run_in_executor(
        None, render_math_inline, text
    )
    yield rendered


async def render_math_block_stream(text):
    """Async generator that yields each line of rendered block math.
    
    Lines are rendered one by one, allowing the TUI to display them
    as they become available.
    """
    lines = text.strip().split("\n")
    for line in lines:
        rendered_line = await asyncio.get_event_loop().run_in_executor(
            None, render_math_inline, line
        )
        yield rendered_line


async def render_latex_stream(text):
    """Async generator that yields rendered LaTeX content incrementally.
    
    Non-math text is yielded as-is; math blocks/inline expressions are
    rendered and yielded as soon as they are processed.
    """
    from interface.textual_ui.ansi_markdown import detect_math_blocks
    blocks = detect_math_blocks(text)
    if not blocks:
        yield text
        return
    last = 0
    for content, is_block, start, end in blocks:
        # Yield any non-math text before this block
        if start > last:
            yield text[last:start]
        # Render and yield the math content
        if is_block:
            async for line in render_math_block_stream(content):
                yield f"⟦{line}⟧"
        else:
            async for chunk in render_math_inline_stream(content):
                yield f"⟦{chunk}⟧"
        last = end
    # Yield any remaining non-math text
    if last < len(text):
        yield text[last:]
