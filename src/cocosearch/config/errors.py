"""Error formatting for configuration validation."""

from difflib import get_close_matches
from pathlib import Path

from pydantic import ValidationError

# Valid field names for each configuration section
VALID_FIELDS = {
    "root": ["indexName", "indexing", "search", "embedding"],
    "indexing": [
        "includePatterns",
        "excludePatterns",
        "languages",
        "chunkSize",
        "chunkOverlap",
    ],
    "search": ["resultLimit", "minScore"],
    "embedding": ["model"],
}


def suggest_field_name(unknown: str, section: str = "root") -> str | None:
    """Suggest a valid field name for an unknown field using fuzzy matching.

    Args:
        unknown: The unknown field name to find a suggestion for.
        section: The configuration section to search in (default: "root").

    Returns:
        Suggested field name if a close match is found, None otherwise.
    """
    valid_fields = VALID_FIELDS.get(section, [])
    matches = get_close_matches(unknown, valid_fields, n=1, cutoff=0.6)
    return matches[0] if matches else None


def format_validation_errors(
    exc: ValidationError, config_path: Path | None = None
) -> str:
    """Format Pydantic validation errors into user-friendly messages.

    Args:
        exc: The Pydantic ValidationError to format.
        config_path: Optional path to the config file for context.

    Returns:
        Formatted error message string with all validation errors.
    """
    # Build header
    if config_path:
        lines = [f"Configuration errors in {config_path}:"]
    else:
        lines = ["Configuration errors:"]

    # Process each error
    for error in exc.errors():
        # Build field path from location tuple
        loc = error["loc"]
        if loc:
            field_path = ".".join(str(part) for part in loc)
        else:
            field_path = "(root)"

        error_type = error["type"]
        error_msg = error["msg"]

        # Handle unknown field errors with suggestions
        if error_type == "extra_forbidden":
            # Extract the field name from the location
            field_name = str(loc[-1]) if loc else ""

            # Determine the section (parent in loc or root)
            if len(loc) > 1:
                section = str(loc[-2])
            else:
                section = "root"

            # Try to suggest a correction
            suggestion = suggest_field_name(field_name, section)
            if suggestion:
                lines.append(
                    f"  - {field_path}: Unknown field. Did you mean '{suggestion}'?"
                )
            else:
                lines.append(f"  - {field_path}: Unknown field")

        # Handle type errors
        elif "type" in error_type:
            # Extract type information from error message or context
            # Pydantic provides expected type in the error details
            ctx = error.get("ctx", {})
            if "expected" in ctx:
                expected = ctx["expected"]
                lines.append(f"  - {field_path}: Expected {expected}")
            else:
                # Fallback: parse from error message or use generic message
                lines.append(f"  - {field_path}: Type error - {error_msg}")

        # Handle all other errors
        else:
            lines.append(f"  - {field_path}: {error_msg}")

    return "\n".join(lines)
