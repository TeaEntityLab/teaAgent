"""Tab completion functions for the chat REPL."""

from __future__ import annotations

from pathlib import Path


def complete_file_path(text: str, root: Path) -> list[str]:
    """Complete file paths starting with @.

    Args:
        text: The text to complete (including @ prefix)
        root: The workspace root directory

    Returns:
        List of completion suggestions
    """
    if not text.startswith('@'):
        return []

    # Remove @ prefix and get partial path
    partial_path = text[1:]

    # Determine the directory to search
    if '/' in partial_path:
        # Has directory component
        dir_part = partial_path.rsplit('/', 1)[0]
        file_part = partial_path.rsplit('/', 1)[1] if '/' in partial_path else ''
        search_dir = root / dir_part
    else:
        # Just filename in root
        dir_part = ''
        file_part = partial_path
        search_dir = root

    # Ensure search directory exists and is within root
    try:
        search_dir = search_dir.resolve()
        if not search_dir.exists() or not search_dir.is_dir():
            return []
        if not search_dir.is_relative_to(root.resolve()):
            return []
    except Exception:
        return []

    # Get matching files and directories
    completions = []
    try:
        for item in search_dir.iterdir():
            # Skip hidden files/directories (except .teaagent)
            if item.name.startswith('.') and item.name != '.teaagent':
                continue

            # Check if matches partial
            if item.name.lower().startswith(file_part.lower()):
                # Build completion path
                if dir_part:
                    completion = f'@{dir_part}/{item.name}'
                else:
                    completion = f'@{item.name}'

                # Add trailing slash for directories
                if item.is_dir():
                    completion += '/'

                completions.append(completion)
    except (OSError, PermissionError) as exc:
        # Log but don't crash completion - filesystem errors are expected in some scenarios
        import logging
        logging.getLogger(__name__).debug('File completion error: %s', exc)

    return sorted(completions)


def complete_symbol(text: str, root: Path) -> list[str]:
    """Complete symbol names (classes, functions) starting with @.

    Args:
        text: The text to complete (including @ prefix)
        root: The workspace root directory

    Returns:
        List of completion suggestions
    """
    if not text.startswith('@'):
        return []

    # Remove @ prefix and get partial symbol name
    partial_symbol = text[1:]

    # Try to use code ontology if available
    try:
        from teaagent.code_ontology import CodeOntologyBuilder

        # Build ontology for the workspace
        builder = CodeOntologyBuilder(root)
        builder.build_from_directory()
        ontology = builder

        # Get all nodes (symbols)
        completions = []
        for node in ontology.nodes:
            # Check if symbol name matches partial
            if node.name.lower().startswith(partial_symbol.lower()):
                # Format: @symbol_name (in file_path)
                completion = f'@{node.name}'
                completions.append(completion)

        return sorted(set(completions))
    except Exception:
        # Fallback: simple file-based symbol search
        return []
