# utils/parsing_utils.py
import logging

logger = logging.getLogger(__name__)

def parse_tuple_str(tuple_str: str | None, expected_len: int, item_type=int) -> tuple | None:
    """
    Parses a string like "8,8" or "50,150" into a tuple of specified type and length.
    Returns None on error, empty string, or None input.
    """
    if not isinstance(tuple_str, str) or not tuple_str.strip():
        return None
    parts = tuple_str.strip().split(',')
    if len(parts) != expected_len:
        logger.warning(f"Parsing tuple string '{tuple_str}': Expected {expected_len} parts, got {len(parts)}.")
        return None
    try:
        parsed_items = [item_type(p.strip()) for p in parts]
        return tuple(parsed_items)
    except (ValueError, TypeError):
        logger.warning(f"Parsing tuple string '{tuple_str}': Error converting parts to {item_type.__name__}.")
        return None
    except Exception as e:
        logger.error(f"Unexpected error parsing tuple string '{tuple_str}': {e}", exc_info=True)
        return None
