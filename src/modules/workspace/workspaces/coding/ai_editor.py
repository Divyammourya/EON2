"""
AI-driven code editing for the Coding Workspace.
"""

from __future__ import annotations

import re

from src.modules.ai.manager import AIManager

_CODE_FENCE = re.compile(
    r"```(?:[a-zA-Z0-9_+-]*)\s*\n(.*?)```",
    re.DOTALL,
)

_SYSTEM_PROMPT = (
    "You are a code editing engine embedded inside a developer tool. "
    "You are given the current source of a single symbol (a function, "
    "method, or class), an instruction describing how it should "
    "change, and sometimes additional project context (the file's "
    "imports, sibling symbols, and other places in the project that "
    "reference this symbol). Use that context to keep the edit "
    "consistent with how the symbol is actually used elsewhere. "
    "Respond with ONLY the complete replacement source for the "
    "symbol - no explanation, no markdown code fences, no "
    "surrounding prose. The symbol's name, signature-level meaning, "
    "and indentation level must be preserved unless the instruction "
    "explicitly asks otherwise. The output must be syntactically "
    "valid on its own."
)


class AICodeEditor:
    """
    Turns a natural-language edit instruction into replacement source
    for a single symbol, using a chat-capable AI provider.

    Deliberately narrow: this class's only responsibility is prompting
    the model and extracting code from its reply. It knows nothing
    about locating symbols, formatting, validating, or writing files —
    that stays with `CodeEditEngine` and `PatchEngine`, which every
    edit goes through identically whether the replacement text came
    from this class or was supplied literally.
    """

    def __init__(
        self,
        ai: AIManager | None = None,
    ) -> None:
        self._ai = ai or AIManager()

    def generate_replacement(
        self,
        *,
        symbol: str,
        current_source: str,
        instruction: str,
        context: str = "",
        language: str = "python",
    ) -> str:
        """
        Ask the model to rewrite `current_source` (the existing body
        of `symbol`) according to `instruction`, and return just the
        replacement source.

        `context` is optional surrounding-project information (e.g.
        from `SymbolContextBuilder`) — the file's imports, sibling
        symbols, and other places in the project that reference this
        symbol. Passing it lets the model make edits that stay
        consistent with how the symbol is actually used elsewhere,
        instead of reasoning about it in isolation.
        """

        user_content = (
            f"Language: {language}\n"
            f"Symbol: {symbol}\n\n"
            f"Current source:\n{current_source}\n\n"
            f"Instruction: {instruction}"
        )

        if context:
            user_content += f"\n\nProject context:\n{context}"

        messages = [
            {
                "role": "system",
                "content": _SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_content,
            },
        ]

        reply = self._ai.chat(messages)

        return self._extract_code(reply)

    def _extract_code(self, reply: str) -> str:
        """
        Strip a markdown code fence if the model added one despite
        being asked not to. Falls back to the raw, trimmed reply.
        """

        match = _CODE_FENCE.search(reply)

        if match:
            return match.group(1).strip()

        return reply.strip()
