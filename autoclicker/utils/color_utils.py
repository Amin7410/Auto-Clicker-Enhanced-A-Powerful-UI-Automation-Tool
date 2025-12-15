# utils/color_utils.py
import logging

logger = logging.getLogger(__name__)

def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """
    Convert a hex color code string (e.g., "#RRGGBB" or "#RGB") to an RGB tuple (0-255).

    Args:
        hex_color (str): The hex color string, optionally starting with '#'.

    Returns:
        tuple[int, int, int]: The RGB tuple (R, G, B).

    Raises:
        ValueError: If the hex color string format is invalid.
    """
    if not isinstance(hex_color, str):
         raise ValueError(f"Input must be a string, got {type(hex_color)}.")

    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 3:
        hex_color = ''.join([c*2 for c in hex_color])
    elif len(hex_color) != 6:
        raise ValueError(f"Invalid hex color format: '{hex_color}'. Must be 3 or 6 hexadecimal characters.")

    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return (r, g, b)
    except ValueError as e:
         raise ValueError(f"Invalid hexadecimal characters in color code '{hex_color}': {e}") from e
    except Exception as e:
         logger.error(f"Unexpected error converting hex '{hex_color}' to RGB: {e}.", exc_info=True)
         raise ValueError(f"Unexpected error converting hex color: {e}") from e


def rgb_to_hex(rgb_color: tuple[int, int, int]) -> str:
    """
    Convert an RGB tuple (0-255 values) to a hex color code string (e.g., "#RRGGBB").

    Args:
        rgb_color (tuple[int, int, int]): The RGB tuple (R, G, B).

    Returns:
        str: The hex color string.

    Raises:
        ValueError: If the input is not a 3-element tuple of integers within the valid range (0-255).
    """
    if not isinstance(rgb_color, tuple) or len(rgb_color) != 3:
        raise ValueError(f"Input must be a 3-element tuple, got {type(rgb_color)} with length {len(rgb_color) if isinstance(rgb_color, (list, tuple)) else 'N/A'}.")

    try:
        r, g, b = rgb_color
        if not all(isinstance(c, int) and 0 <= c <= 255 for c in [r, g, b]):
            raise ValueError(f"Tuple elements must be integers between 0 and 255, got: {rgb_color}.")

        return '#{:02x}{:02x}{:02x}'.format(r, g, b)
    except ValueError:
         raise
    except Exception as e:
         logger.error(f"Unexpected error converting RGB {rgb_color} to hex: {e}.", exc_info=True)
         raise ValueError(f"Unexpected error converting RGB color: {e}") from e


if __name__ == '__main__':

    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(__main__)s - %(message)s')
    logger = logging.getLogger(__name__)
    logger.info("--- Color Utils Test ---")

    print("\n--- Testing hex_to_rgb ---")
    try:
        print("#FF0000 ->", hex_to_rgb("#FF0000"))
        print("#00FF00 ->", hex_to_rgb("#00FF00"))
        print("#0000FF ->", hex_to_rgb("#0000FF"))
        print("#FFFFFF ->", hex_to_rgb("#FFFFFF"))
        print("#000000 ->", hex_to_rgb("#000000"))
        print("#F00 ->", hex_to_rgb("#F00")) 
        print("#abc ->", hex_to_rgb("#abc"))
        print("#1A2B3C ->", hex_to_rgb("#1A2B3C"))
        print("1A2B3C (no #) ->", hex_to_rgb("1A2B3C"))

        try: hex_to_rgb("invalid")
        except ValueError as e: print(f"Caught expected error for 'invalid': {e}")
        try: hex_to_rgb("#GGGGGG")
        except ValueError as e: print(f"Caught expected error for '#GGGGGG': {e}")
        try: hex_to_rgb("#12345")
        except ValueError as e: print(f"Caught expected error for '#12345': {e}")
        try: hex_to_rgb(123)
        except ValueError as e: print(f"Caught expected error for 123 (int): {e}")

    except Exception as e:
        logger.error(f"Unexpected error during hex_to_rgb test: {e}", exc_info=True)


    print("\n--- Testing rgb_to_hex ---")
    try:
        print("(255, 0, 0) ->", rgb_to_hex((255, 0, 0)))
        print("(0, 255, 0) ->", rgb_to_hex((0, 255, 0)))
        print("(0, 0, 255) ->", rgb_to_hex((0, 0, 255)))
        print("(255, 255, 255) ->", rgb_to_hex((255, 255, 255)))
        print("(0, 0, 0) ->", rgb_to_hex((0, 0, 0)))
        print("(26, 43, 60) ->", rgb_to_hex((26, 43, 60)))

        try: rgb_to_hex((256, 0, 0))
        except ValueError as e: print(f"Caught expected error for (256, 0, 0): {e}")
        try: rgb_to_hex((-1, 0, 0)) 
        except ValueError as e: print(f"Caught expected error for (-1, 0, 0): {e}")
        try: rgb_to_hex((10, 20)) 
        except ValueError as e: print(f"Caught expected error for (10, 20): {e}")
        try: rgb_to_hex([10, 20, 30]) 
        except ValueError as e: print(f"Caught expected error for [10, 20, 30]: {e}")
        try: rgb_to_hex("color") 
        except ValueError as e: print(f"Caught expected error for 'color': {e}")


    except Exception as e:
        logger.error(f"Unexpected error during rgb_to_hex test: {e}", exc_info=True)


    print("\nColor Utils test finished.")
