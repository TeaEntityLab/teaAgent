"""Shell-command normalization for approval pattern matching.

Pure function with no state. Moved unchanged from ``teaagent.approval.manager``
(A-P1-6 split, ADR-0044). ``teaagent.approval.manager`` re-exports the name.
"""

from __future__ import annotations

import re
import shlex


def _normalize_shell_arg(command: str) -> str:
    """Normalize a shell command string through multiple passes to defeat obfuscation.

    Applies successive normalization to catch:
    - Quoted strings: rm -r"f" /prod -> rm -rf /prod
    - Backtick injection: `echo /prod` -> /prod
    - Subshell expansion: $(echo /prod) -> /prod
    - Escaped characters: r\\m -> rm
    - Double-encoded sequences
    """
    if not command:
        return command

    normalized = command

    # Extract subshell content from ORIGINAL command BEFORE $VAR stripping
    # (Pass 3/4).  This prevents Pass 0 from consuming e.g. $rm from
    # $(rm -rf /prod), which would lose the dangerous verb.
    backtick_contents = re.findall(r'`([^`]*)`', command)
    dollar_contents = re.findall(r'\$\(([^)]*)\)', command)
    process_sub_contents = re.findall(r'<\(([^)]*)\)', command)

    # Pass 0: Strip shell environment variable references
    # $VAR or ${VAR} -> '' (shell evaluates unset vars as empty)
    # Must run BEFORE quote stripping so $u'rod' -> 'rod' -> rod
    normalized = re.sub(r'\$\{[a-zA-Z_][a-zA-Z0-9_]*\}', '', normalized)
    normalized = re.sub(r'\$[a-zA-Z_][a-zA-Z0-9_]*', '', normalized)

    # Pass 1: Strip surrounding quotes from each token
    # "foo" -> foo, 'bar' -> bar
    normalized = re.sub(r"""(["'])(.*?)\1""", r'\2', normalized)

    # Pass 2: Remove backslash escapes: \r -> r, \" -> "
    normalized = re.sub(r'\\(.)', r'\1', normalized)

    # Pass 3/4 were moved before Pass 0 — extraction now happens above.

    # Pass 4b: Expand brace patterns like /pr{od,oduction} -> /prod /production
    def _expand_braces(s: str) -> str:
        """Expand simple brace alternation: a{b,c}d -> abd acd"""
        match = re.search(r'\{([^{}]+)\}', s)
        if not match:
            return s
        prefix = s[: match.start()]
        suffix = s[match.end() :]
        alternatives = match.group(1).split(',')
        expanded = ' '.join(prefix + alt.strip() + suffix for alt in alternatives)
        # Recurse for nested braces (one level)
        return _expand_braces(expanded) if '{' in expanded else expanded

    brace_expanded = _expand_braces(normalized)

    # Pass 5: Try shlex split for final normalization
    try:
        tokens = shlex.split(normalized)
        # Collapse adjacent single-char flags: rm -r -f -> rm -rf
        collapsed: list[str] = []
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            if tok.startswith('-') and len(tok) == 2 and tok != '--':
                merged = tok
                i += 1
                while (
                    i < len(tokens)
                    and tokens[i].startswith('-')
                    and len(tokens[i]) == 2
                    and tokens[i] != '--'
                ):
                    merged += tokens[i][1:]
                    i += 1
                collapsed.append(merged)
            else:
                collapsed.append(tok)
                i += 1
        normalized = ' '.join(collapsed).lower()
    except ValueError:
        normalized = normalized.lower()

    # Combine: check the main normalized string PLUS any extracted subshell contents
    all_variants = [normalized]
    if brace_expanded != normalized:
        all_variants.append(brace_expanded.lower())
    for content in backtick_contents + dollar_contents + process_sub_contents:
        # Recursively normalize subshell contents to catch nested patterns
        all_variants.append(_normalize_shell_arg(content))

    return ' | '.join(all_variants)
