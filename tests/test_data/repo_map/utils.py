"""String utilities."""


def capitalize_words(text: str) -> str:
    """Capitalize the first letter of each word."""
    return ' '.join(word.capitalize() for word in text.split())


def truncate(text: str, max_len: int, suffix: str = '...') -> str:
    """Truncate text to max_len, appending suffix if shortened."""
    if len(text) <= max_len:
        return text
    return text[:max_len - len(suffix)] + suffix


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    return text.lower().replace(' ', '-')
