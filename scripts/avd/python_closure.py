from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable


class PythonClosureError(RuntimeError):
    pass


_DYNAMIC_CALL_NAMES = {"__import__", "eval", "exec"}
_DYNAMIC_CALL_ATTRS = {
    "import_module",
    "spec_from_file_location",
    "SourceFileLoader",
    "SourcelessFileLoader",
    "run_module",
    "run_path",
}
_DYNAMIC_IMPORT_FROM_MODULES = {
    "importlib": {"import_module"},
    "importlib.util": {"spec_from_file_location"},
    "importlib.machinery": {"SourceFileLoader", "SourcelessFileLoader"},
    "runpy": {"run_module", "run_path"},
}


def _module_candidates(repo_root: Path, module: str) -> tuple[Path, ...]:
    parts = module.split(".")
    base = repo_root.joinpath(*parts)
    return (base.with_suffix(".py"), base / "__init__.py")


def _resolve_module(repo_root: Path, module: str) -> Path | None:
    if not module or any(part in {"", ".", ".."} for part in module.split(".")):
        return None
    matches = [candidate for candidate in _module_candidates(repo_root, module) if candidate.is_file()]
    if len(matches) > 1:
        raise PythonClosureError(f"AMBIGUOUS_LOCAL_MODULE:{module}")
    return matches[0] if matches else None


def _module_name(repo_root: Path, path: Path) -> tuple[str, bool]:
    rel = path.relative_to(repo_root)
    if rel.suffix != ".py":
        raise PythonClosureError(f"NON_PYTHON_MODULE:{rel.as_posix()}")
    parts = list(rel.with_suffix("").parts)
    is_package = parts[-1] == "__init__"
    if is_package:
        parts = parts[:-1]
    if not parts:
        raise PythonClosureError("ROOT_INIT_MODULE_FORBIDDEN")
    return ".".join(parts), is_package


def _package_initializers(repo_root: Path, module: str, *, module_is_package: bool) -> tuple[Path, ...]:
    parts = module.split(".")
    package_parts = parts if module_is_package else parts[:-1]
    out: list[Path] = []
    for depth in range(1, len(package_parts) + 1):
        init = repo_root.joinpath(*package_parts[:depth]) / "__init__.py"
        if init.is_file():
            out.append(init)
    return tuple(out)


def _relative_base(current_module: str, current_is_package: bool, level: int) -> str:
    package = current_module if current_is_package else current_module.rpartition(".")[0]
    parts = package.split(".") if package else []
    if level <= 0:
        raise PythonClosureError("INVALID_RELATIVE_IMPORT_LEVEL")
    remove = level - 1
    if remove > len(parts):
        raise PythonClosureError(
            f"RELATIVE_IMPORT_ESCAPES_PACKAGE:{current_module}:level={level}"
        )
    base = parts[: len(parts) - remove] if remove else parts
    if not base:
        raise PythonClosureError(
            f"RELATIVE_IMPORT_ESCAPES_PACKAGE:{current_module}:level={level}"
        )
    return ".".join(base)


def _dynamic_import_guard(tree: ast.AST, rel: str) -> None:
    dynamic_bound_names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        allowed = _DYNAMIC_IMPORT_FROM_MODULES.get(node.module or "")
        if not allowed:
            continue
        for alias in node.names:
            if alias.name in allowed:
                dynamic_bound_names.add(alias.asname or alias.name)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and (
            func.id in _DYNAMIC_CALL_NAMES or func.id in dynamic_bound_names
        ):
            raise PythonClosureError(f"DYNAMIC_IMPORT_FORBIDDEN:{rel}:{func.id}")
        if isinstance(func, ast.Attribute) and func.attr in _DYNAMIC_CALL_ATTRS:
            raise PythonClosureError(f"DYNAMIC_IMPORT_FORBIDDEN:{rel}:{func.attr}")


def _local_imports(repo_root: Path, path: Path) -> tuple[str, ...]:
    rel = path.relative_to(repo_root).as_posix()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise PythonClosureError(f"PYTHON_PARSE_FAILURE:{rel}") from exc

    _dynamic_import_guard(tree, rel)
    current_module, current_is_package = _module_name(repo_root, path)
    discovered: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name
                if _resolve_module(repo_root, module) is not None:
                    discovered.add(module)
                elif module.startswith("scripts."):
                    raise PythonClosureError(f"UNRESOLVED_LOCAL_IMPORT:{rel}:{module}")

        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = _relative_base(current_module, current_is_package, node.level)
                module = f"{base}.{node.module}" if node.module else base
                resolved = _resolve_module(repo_root, module)
                if node.module is not None:
                    if resolved is None:
                        raise PythonClosureError(f"UNRESOLVED_LOCAL_IMPORT:{rel}:{module}")
                    discovered.add(module)
                else:
                    # `from . import child`: each alias may be a child module or
                    # an attribute exported by the package initializer.
                    package_init = _resolve_module(repo_root, base)
                    for alias in node.names:
                        if alias.name == "*":
                            if package_init is None:
                                raise PythonClosureError(
                                    f"UNRESOLVED_LOCAL_IMPORT:{rel}:{base}:*"
                                )
                            continue
                        child = f"{base}.{alias.name}"
                        if _resolve_module(repo_root, child) is not None:
                            discovered.add(child)
                        elif package_init is None:
                            raise PythonClosureError(
                                f"UNRESOLVED_LOCAL_IMPORT:{rel}:{child}"
                            )
            else:
                module = node.module or ""
                resolved = _resolve_module(repo_root, module)
                if resolved is not None:
                    discovered.add(module)
                    # `from package import child` can load child as a submodule.
                    if resolved.name == "__init__.py":
                        for alias in node.names:
                            if alias.name == "*":
                                continue
                            child = f"{module}.{alias.name}"
                            if _resolve_module(repo_root, child) is not None:
                                discovered.add(child)
                elif module.startswith("scripts."):
                    raise PythonClosureError(f"UNRESOLVED_LOCAL_IMPORT:{rel}:{module}")

    return tuple(sorted(discovered))


def discover_python_closure(repo_root: Path, entry_modules: Iterable[str]) -> tuple[str, ...]:
    """Discover deterministic transitive Python source closure for judge code.

    Local modules are resolved from the repository itself. Existing package
    initializers are included and traversed because import-time code is
    executable. Dynamic import/code-loading primitives fail closed: a static
    content commitment cannot safely claim completeness when runtime module
    discovery is opaque.
    """
    repo_root = repo_root.resolve()
    if not repo_root.is_dir():
        raise PythonClosureError("REPOSITORY_ROOT_NOT_DIRECTORY")

    queue = sorted(set(entry_modules))
    if not queue:
        raise PythonClosureError("EMPTY_ENTRYPOINT_SET")

    visited_modules: set[str] = set()
    committed_paths: set[Path] = set()
    traversed_paths: set[Path] = set()

    while queue:
        module = queue.pop(0)
        if module in visited_modules:
            continue
        path = _resolve_module(repo_root, module)
        if path is None:
            raise PythonClosureError(f"UNRESOLVED_ENTRY_MODULE:{module}")
        resolved = path.resolve()
        try:
            resolved.relative_to(repo_root)
        except ValueError as exc:
            raise PythonClosureError(f"MODULE_ESCAPES_REPOSITORY:{module}") from exc
        if path.is_symlink():
            raise PythonClosureError(f"SYMLINK_MODULE_FORBIDDEN:{module}")

        current_name, is_package = _module_name(repo_root, resolved)
        if current_name != module:
            raise PythonClosureError(
                f"MODULE_PATH_IDENTITY_MISMATCH:{module}:{current_name}"
            )

        visited_modules.add(module)
        executable_paths = [resolved]
        executable_paths.extend(
            init.resolve()
            for init in _package_initializers(
                repo_root, module, module_is_package=is_package
            )
        )

        for executable_path in sorted(
            set(executable_paths),
            key=lambda item: item.relative_to(repo_root).as_posix(),
        ):
            try:
                executable_path.relative_to(repo_root)
            except ValueError as exc:
                raise PythonClosureError(
                    f"MODULE_ESCAPES_REPOSITORY:{module}"
                ) from exc
            committed_paths.add(executable_path)
            if executable_path in traversed_paths:
                continue
            traversed_paths.add(executable_path)
            for dependency in _local_imports(repo_root, executable_path):
                if dependency not in visited_modules and dependency not in queue:
                    queue.append(dependency)
        queue.sort()

    return tuple(
        sorted(path.relative_to(repo_root).as_posix() for path in committed_paths)
    )
