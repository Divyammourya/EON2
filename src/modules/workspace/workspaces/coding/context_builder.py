"""
Cross-file context for AI-driven code edits.

Gives `AICodeEditor` more to work with than a symbol's own source: the
target file's imports, its sibling symbols, and other files in the
project that reference the symbol being edited. Consumes
`RepositoryIndexer` and `SymbolIndexer` rather than walking the
filesystem or re-parsing symbols itself — file discovery and symbol
extraction are already those classes' jobs.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from .models import SymbolKind
from .repository_indexer import RepositoryIndexer
from .symbol_indexer import SymbolIndexer

# How many cross-file caller references to collect before stopping.
# Kept small and fixed: this context is for grounding a single-symbol
# edit, not for a full usage report.
_DEFAULT_MAX_CALLERS = 5


def _build_parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST | None]:
    """
    Build a node -> immediate-parent map for `tree`.

    `ast.walk` alone doesn't expose parent links, and both usage
    classification (call vs. plain read vs. reassignment) and
    receiver-type resolution (walking up to the enclosing function or
    module scope) need them.
    """

    parent_map: dict[ast.AST, ast.AST | None] = {tree: None}

    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parent_map[child] = parent

    return parent_map


class SymbolUsage(str, Enum):
    """
    How a matched reference to a symbol is actually being used,
    determined from its immediate parent AST node.
    """

    CALL = "call"
    ATTRIBUTE_CALL = "attribute call"
    ASSIGNMENT_TARGET = "reassigned"
    IMPORT = "imported only"
    READ = "read"


@dataclass(slots=True)
class CallerReference:
    """
    A single place elsewhere in the project that references a symbol
    by name.
    """

    file: Path
    line: int
    snippet: str
    usage: SymbolUsage = SymbolUsage.READ
    positional_args: int | None = None
    keyword_args: tuple[str, ...] = ()
    # Set only for ATTRIBUTE_CALL usages where the receiver's class
    # could be resolved unambiguously (see
    # SymbolContextBuilder._resolve_receiver_class). None otherwise —
    # including for every other usage kind, and for attribute calls
    # where the receiver's type couldn't be determined.
    receiver_class: str | None = None

    def describe_usage(self) -> str:
        """
        Human-readable summary of `usage`, including call-argument
        shape and, when known, the receiver's resolved class, for use
        in `EditContext.render()`.
        """

        if self.usage in (SymbolUsage.CALL, SymbolUsage.ATTRIBUTE_CALL):
            details: list[str] = []

            if self.usage is SymbolUsage.ATTRIBUTE_CALL and self.receiver_class:
                details.append(f"on {self.receiver_class}")

            if self.positional_args:
                details.append(f"{self.positional_args} positional")

            if self.keyword_args:
                details.append("kwargs: " + ", ".join(self.keyword_args))

            suffix = f" ({', '.join(details)})" if details else ""
            return f"{self.usage.value}{suffix}"

        return self.usage.value


@dataclass(slots=True)
class EditContext:
    """
    Cross-file context gathered for a single symbol edit.
    """

    symbol: str
    file: Path
    imports: list[str] = field(default_factory=list)
    siblings: list[str] = field(default_factory=list)
    callers: list[CallerReference] = field(default_factory=list)

    def render(self) -> str:
        """
        Render this context as plain text suitable for inclusion in
        an AI prompt. Sections with nothing to say are omitted.
        """

        parts: list[str] = []

        if self.imports:
            parts.append(
                "Imports in this file:\n" + "\n".join(self.imports)
            )

        if self.siblings:
            parts.append(
                "Other symbols defined in this file: "
                + ", ".join(self.siblings)
            )

        if self.callers:
            caller_lines = "\n".join(
                f"{caller.file} (line {caller.line}) "
                f"[{caller.describe_usage()}]: {caller.snippet}"
                for caller in self.callers
            )
            parts.append(
                f"Other places in the project that reference "
                f"'{self.symbol}':\n{caller_lines}"
            )

        return "\n\n".join(parts)


@dataclass(slots=True)
class _ImportBindings:
    """
    What a single candidate file's import statements resolve to,
    relative to the module that defines the symbol being edited.

    Built once per candidate file so `_find_callers` can tell an
    actual reference to the target symbol apart from an unrelated
    local variable or a same-named import from a different module.
    """

    # True only if this file has an unaliased `from <target_module>
    # import <symbol>` (or `... import <original> as <symbol>`)
    # binding `symbol` itself — i.e. a bare `symbol` Name reference
    # in this file's body can actually resolve to it.
    imports_target_symbol: bool

    # Local names bound to the target module itself, e.g. the `t` in
    # `import target_module as t`. Not currently required for a
    # match, but kept for symmetry with `other_module_names` and any
    # future stricter attribute resolution.
    target_module_aliases: frozenset[str]

    # Local names bound to some *other* module. Used only to rule
    # out `some_other_module.symbol` attribute accesses that merely
    # share the symbol's name.
    other_module_names: frozenset[str]

    # Line of the `from <target_module> import <symbol>` statement
    # itself, when `imports_target_symbol` is True. Used to report an
    # IMPORT-only caller if the file imports the symbol but never
    # otherwise references it as a Name/Attribute.
    import_line: int | None


class SymbolContextBuilder:
    """
    Builds an `EditContext` for a symbol about to be edited.

    One responsibility: gather the surrounding context a model needs
    to edit a symbol safely across a project, not just in isolation.
    Does not itself talk to the AI, edit files, or apply patches.
    """

    def __init__(
        self,
        repository_indexer: RepositoryIndexer,
        symbol_indexer: SymbolIndexer,
        *,
        max_callers: int = _DEFAULT_MAX_CALLERS,
    ) -> None:
        self._repository_indexer = repository_indexer
        self._symbol_indexer = symbol_indexer
        self._max_callers = max_callers

    def build(
        self,
        *,
        file: Path,
        symbol: str,
    ) -> EditContext:
        """
        Gather imports, sibling symbols, and cross-file callers for
        `symbol`, defined in `file`.
        """

        source = file.read_text(encoding="utf-8")

        return EditContext(
            symbol=symbol,
            file=file,
            imports=self._extract_imports(source),
            siblings=self._sibling_symbols(file, symbol),
            callers=self._find_callers(file, symbol),
        )

    def _extract_imports(self, source: str) -> list[str]:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []

        return [
            ast.unparse(node)
            for node in tree.body
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ]

    def _sibling_symbols(self, file: Path, symbol: str) -> list[str]:
        relative = self._relative_path(file)

        if relative is None:
            return []

        return [
            candidate.name
            for candidate in self._symbol_indexer.symbols_in_file(relative)
            if candidate.name != symbol
        ]

    def _find_callers(
        self,
        file: Path,
        symbol: str,
    ) -> list[CallerReference]:
        repository_index = self._repository_indexer.get_index()

        target_relative = self._relative_path(file)
        target_module = (
            self._module_name(target_relative)
            if target_relative is not None
            else None
        )

        callers: list[CallerReference] = []

        for indexed_file in repository_index.files:
            if indexed_file.language != "python":
                continue

            if indexed_file.path == file:
                continue

            try:
                text = indexed_file.path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue

            # If we can't place the target file relative to the
            # project root, we have no basis for import resolution.
            # Fall back to identifier-only matching rather than
            # silently dropping every candidate file.
            bindings = (
                self._collect_import_bindings(
                    tree,
                    indexed_file.relative_path,
                    target_module,
                    symbol,
                )
                if target_module is not None
                else None
            )

            lines = text.splitlines()
            found_reference = False
            parent_map = _build_parent_map(tree)

            for node in ast.walk(tree):
                parent = parent_map.get(node)
                receiver_class: str | None = None

                if isinstance(node, ast.Name) and node.id == symbol:
                    if bindings is not None and not bindings.imports_target_symbol:
                        # A bare name that isn't actually bound to an
                        # import of our target symbol — a local
                        # variable, parameter, or an unrelated import
                        # that merely shares the name.
                        continue

                    usage, positional, keywords = self._classify_usage(
                        node, parent, attribute=False,
                    )
                elif isinstance(node, ast.Attribute) and node.attr == symbol:
                    if (
                        bindings is not None
                        and isinstance(node.value, ast.Name)
                        and node.value.id in bindings.other_module_names
                    ):
                        # `some_other_module.symbol` — an attribute
                        # access on a *known, different* module, so
                        # it can't be our target symbol. Anything
                        # else (instance attribute/method access,
                        # e.g. `agent.ai_edit_symbol(...)`) is kept:
                        # we have no type information to resolve it
                        # further, same limitation SymbolIndexer's
                        # own find_symbol() documents for methods.
                        continue

                    usage, positional, keywords = self._classify_usage(
                        node, parent, attribute=True,
                    )

                    if usage is SymbolUsage.ATTRIBUTE_CALL:
                        receiver_class = self._resolve_receiver_class(
                            node, parent_map, symbol,
                        )
                else:
                    continue

                found_reference = True
                line_number = node.lineno
                snippet = (
                    lines[line_number - 1].strip()
                    if 0 < line_number <= len(lines)
                    else ""
                )

                callers.append(
                    CallerReference(
                        file=indexed_file.relative_path,
                        line=line_number,
                        snippet=snippet,
                        usage=usage,
                        positional_args=positional,
                        keyword_args=keywords,
                        receiver_class=receiver_class,
                    )
                )

                if len(callers) >= self._max_callers:
                    return callers

            if (
                not found_reference
                and bindings is not None
                and bindings.imports_target_symbol
                and bindings.import_line is not None
            ):
                # The file imports the symbol but never references it
                # by name anywhere else we can see — worth flagging
                # as its own usage kind (e.g. a re-export) rather
                # than silently omitting it.
                line_number = bindings.import_line
                snippet = (
                    lines[line_number - 1].strip()
                    if 0 < line_number <= len(lines)
                    else ""
                )

                callers.append(
                    CallerReference(
                        file=indexed_file.relative_path,
                        line=line_number,
                        snippet=snippet,
                        usage=SymbolUsage.IMPORT,
                    )
                )

                if len(callers) >= self._max_callers:
                    return callers

        return callers

    def _classify_usage(
        self,
        node: ast.AST,
        parent: ast.AST | None,
        *,
        attribute: bool,
    ) -> tuple[SymbolUsage, int | None, tuple[str, ...]]:
        """
        Classify a matched Name/Attribute node by its immediate
        parent: a direct call, an assignment target, or a plain read.
        Returns the usage kind plus, for calls, the positional-arg
        count and keyword-arg names.
        """

        if isinstance(parent, ast.Call) and parent.func is node:
            positional = len(parent.args)
            keywords = tuple(
                kw.arg for kw in parent.keywords if kw.arg is not None
            )
            usage = SymbolUsage.ATTRIBUTE_CALL if attribute else SymbolUsage.CALL
            return usage, positional, keywords

        if self._is_assignment_target(node, parent):
            return SymbolUsage.ASSIGNMENT_TARGET, None, ()

        return SymbolUsage.READ, None, ()

    def _is_assignment_target(
        self,
        node: ast.AST,
        parent: ast.AST | None,
    ) -> bool:
        """
        Whether `node` is being assigned to by its immediate parent.

        Covers simple assignment targets only (`symbol = ...`,
        `obj.symbol = ...`, `for symbol in ...`) — a `Name`/
        `Attribute` nested inside a tuple/list unpacking target has a
        `Tuple`/`List` as its immediate parent rather than the
        `Assign` itself, so that case falls through to READ. That's a
        deliberate simplification, not a correctness bug: it under-
        reports reassignments rather than over-reporting them.
        """

        if parent is None:
            return False

        if isinstance(parent, ast.Assign):
            return node in parent.targets

        if isinstance(parent, (ast.AugAssign, ast.AnnAssign)):
            return parent.target is node

        if isinstance(parent, (ast.For, ast.AsyncFor)):
            return parent.target is node

        if isinstance(parent, ast.comprehension):
            return parent.target is node

        return False

    def _resolve_receiver_class(
        self,
        node: ast.Attribute,
        parent_map: dict[ast.AST, ast.AST | None],
        symbol: str,
    ) -> str | None:
        """
        Best-effort resolution of an attribute call's receiver to a
        concrete class name, using only local, syntactic evidence in
        the enclosing function (or module) scope: a parameter/
        variable type annotation, or a `receiver = SomeClass(...)`
        constructor-call assignment.

        Falls back to None whenever the evidence is missing, or the
        resolved class turns out to not exist, be ambiguous (more
        than one class of that name in the project), or not actually
        define `symbol` as a method — this is meant to raise
        confidence on top of `_find_callers`' existing recall, never
        to mislabel a caller.
        """

        if not isinstance(node.value, ast.Name):
            return None

        scope = self._enclosing_scope(node, parent_map)

        if scope is None:
            return None

        class_name = self._declared_receiver_type(scope, node.value.id)

        if class_name is None or not self._class_defines_method(
            class_name, symbol,
        ):
            return None

        return class_name

    def _enclosing_scope(
        self,
        node: ast.AST,
        parent_map: dict[ast.AST, ast.AST | None],
    ) -> ast.FunctionDef | ast.AsyncFunctionDef | ast.Module | None:
        current = parent_map.get(node)

        while current is not None:
            if isinstance(
                current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module),
            ):
                return current

            current = parent_map.get(current)

        return None

    def _declared_receiver_type(
        self,
        scope: ast.FunctionDef | ast.AsyncFunctionDef | ast.Module,
        receiver_name: str,
    ) -> str | None:
        if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
            parameters = (
                *scope.args.posonlyargs,
                *scope.args.args,
                *scope.args.kwonlyargs,
                *((scope.args.vararg,) if scope.args.vararg else ()),
                *((scope.args.kwarg,) if scope.args.kwarg else ()),
            )

            for parameter in parameters:
                if parameter.arg == receiver_name and parameter.annotation is not None:
                    return self._simple_type_name(parameter.annotation)

        for statement in self._statements_in_scope(scope.body):
            if (
                isinstance(statement, ast.AnnAssign)
                and isinstance(statement.target, ast.Name)
                and statement.target.id == receiver_name
                and statement.annotation is not None
            ):
                return self._simple_type_name(statement.annotation)

            if isinstance(statement, ast.Assign) and isinstance(
                statement.value, ast.Call,
            ):
                for target in statement.targets:
                    if isinstance(target, ast.Name) and target.id == receiver_name:
                        class_name = self._constructor_class_name(statement.value)

                        if class_name is not None:
                            return class_name

        return None

    def _statements_in_scope(
        self,
        statements: list[ast.stmt],
    ) -> Iterable[ast.stmt]:
        """
        Yield every statement reachable from `statements` without
        crossing into a nested function/class/lambda scope — those
        introduce their own bindings, which don't apply to the
        receiver name we're resolving in the outer scope.
        """

        for statement in statements:
            yield statement

            if isinstance(
                statement,
                (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda),
            ):
                continue

            for field_name in ("body", "orelse", "finalbody"):
                nested = getattr(statement, field_name, None)

                if nested:
                    yield from self._statements_in_scope(nested)

            for handler in getattr(statement, "handlers", ()):
                yield from self._statements_in_scope(handler.body)

    def _simple_type_name(self, annotation: ast.expr) -> str | None:
        if isinstance(annotation, ast.Name):
            return annotation.id

        if isinstance(annotation, ast.Attribute):
            return annotation.attr

        if isinstance(annotation, ast.Constant) and isinstance(
            annotation.value, str,
        ):
            # A stringified forward-reference annotation, e.g. the
            # "CodingAgent" in `agent: "CodingAgent"`.
            forward_ref = annotation.value.strip()
            return forward_ref.rsplit(".", 1)[-1] if forward_ref else None

        if (
            isinstance(annotation, ast.Subscript)
            and isinstance(annotation.value, ast.Name)
            and annotation.value.id == "Optional"
        ):
            return self._simple_type_name(annotation.slice)

        return None

    def _constructor_class_name(self, call: ast.Call) -> str | None:
        func = call.func

        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr
        else:
            return None

        # Heuristic, not a guarantee: constructor calls target
        # PascalCase names. A lowercase callable is far more likely a
        # factory function, so we don't guess a class name from it.
        return name if name[:1].isupper() else None

    def _class_defines_method(self, class_name: str, method_name: str) -> bool:
        classes = [
            candidate
            for candidate in self._symbol_indexer.find_symbol(class_name)
            if candidate.kind is SymbolKind.CLASS
        ]

        if len(classes) != 1:
            return False  # no such class in the project, or ambiguous

        methods = [
            candidate
            for candidate in self._symbol_indexer.find_symbol(
                f"{class_name}.{method_name}",
            )
            if candidate.kind is SymbolKind.METHOD
        ]

        return len(methods) == 1

    def _collect_import_bindings(
        self,
        tree: ast.AST,
        candidate_relative: Path,
        target_module: str,
        symbol: str,
    ) -> _ImportBindings:
        """
        Walk a candidate file's import statements and resolve each
        one to an absolute, project-rooted dotted module path, so it
        can be compared against `target_module`.
        """

        imports_target_symbol = False
        import_line: int | None = None
        target_module_aliases: set[str] = set()
        other_module_names: set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = self._resolve_relative_import(
                    candidate_relative, node,
                )

                for alias in node.names:
                    bound_name = alias.asname or alias.name

                    if module == target_module and alias.name == symbol:
                        if bound_name == symbol:
                            imports_target_symbol = True
                            import_line = node.lineno
                    elif module and module != target_module:
                        other_module_names.add(bound_name)

            elif isinstance(node, ast.Import):
                for alias in node.names:
                    bound_name = alias.asname or alias.name.split(".")[0]

                    if alias.name == target_module:
                        target_module_aliases.add(bound_name)
                    else:
                        other_module_names.add(bound_name)

        return _ImportBindings(
            imports_target_symbol=imports_target_symbol,
            target_module_aliases=frozenset(target_module_aliases),
            other_module_names=frozenset(other_module_names),
            import_line=import_line,
        )

    def _resolve_relative_import(
        self,
        candidate_relative: Path,
        node: ast.ImportFrom,
    ) -> str:
        """
        Resolve an `ast.ImportFrom` node to an absolute, project-
        rooted dotted module path.

        `node.level == 0` (`from x import y`) is already absolute.
        `node.level >= 1` (`from . import y`, `from ..x import y`) is
        resolved against the package containing `candidate_relative`
        — its parent directory, dotted — walking up one extra
        package per additional level, mirroring CPython's own
        relative-import resolution.
        """

        if node.level == 0:
            return node.module or ""

        package_parts = list(candidate_relative.parent.parts)
        ascend = node.level - 1

        if ascend:
            package_parts = (
                package_parts[: len(package_parts) - ascend]
                if ascend <= len(package_parts)
                else []
            )

        base = ".".join(package_parts)

        if node.module:
            return f"{base}.{node.module}" if base else node.module

        return base

    def _module_name(self, relative_path: Path) -> str:
        """
        Convert a project-relative file path into its dotted module
        path, e.g. `pkg/sub/mod.py` -> `pkg.sub.mod`. `__init__.py`
        represents the package itself, so it collapses to the
        directory's dotted path rather than appending `__init__`.
        """

        parts = list(relative_path.with_suffix("").parts)

        if parts and parts[-1] == "__init__":
            parts = parts[:-1]

        return ".".join(parts)

    def _relative_path(self, file: Path) -> Path | None:
        try:
            return file.relative_to(
                self._repository_indexer.get_index().project_root,
            )
        except ValueError:
            return None
