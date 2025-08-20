"""
Color Generator Service
Generates unique, deterministic colors for tracking objects based on their IDs
"""

import hashlib
import colorsys
from typing import Tuple

class ColorGenerator:
    """Generate unique colors for tracking objects"""
    
    @staticmethod
    def generate_color(object_id: str, object_type: str = 'default') -> str:
        """
        Generate a unique hex color based on object ID
        Uses MD5 hash to ensure same ID always gets same color
        
        Args:
            object_id: Unique identifier (ICAO for aircraft, NORAD ID for satellites)
            object_type: 'aircraft' or 'satellite' to adjust color ranges
            
        Returns:
            Hex color string (e.g., '#FF6600')
        """
        # Create a hash of the ID for deterministic color generation
        hash_obj = hashlib.md5(str(object_id).encode())
        hash_hex = hash_obj.hexdigest()
        
        # Extract values from hash for HSL color components
        # Use different parts of hash for better distribution
        hue_int = int(hash_hex[:8], 16)
        sat_int = int(hash_hex[8:12], 16)
        light_int = int(hash_hex[12:16], 16)
        
        # Adjust hue range based on object type
        if object_type == 'aircraft':
            # Warmer colors (reds, oranges, yellows) - 0-60 and 300-360 degrees
            hue_base = hue_int % 120
            if hue_base > 60:
                hue = 300 + (hue_base - 60)  # 300-360 range
            else:
                hue = hue_base  # 0-60 range
        elif object_type == 'satellite':
            # Cooler colors (greens, blues, purples) - 120-300 degrees
            hue = 120 + (hue_int % 180)
        else:
            # Full spectrum
            hue = hue_int % 360
        
        # High saturation for vibrant colors (70-100%)
        saturation = 70 + (sat_int % 30)
        
        # Good brightness for visibility on dark backgrounds (50-80%)
        lightness = 50 + (light_int % 30)
        
        # Convert HSL to hex
        return ColorGenerator.hsl_to_hex(hue, saturation, lightness)
    
    @staticmethod
    def hsl_to_hex(h: float, s: float, l: float) -> str:
        """
        Convert HSL color to hex string
        
        Args:
            h: Hue (0-360)
            s: Saturation (0-100)
            l: Lightness (0-100)
            
        Returns:
            Hex color string
        """
        # Convert to 0-1 range
        h = h / 360.0
        s = s / 100.0
        l = l / 100.0
        
        # Convert HSL to RGB
        r, g, b = colorsys.hls_to_rgb(h, l, s)
        
        # Convert to 0-255 range and then to hex
        r = int(r * 255)
        g = int(g * 255)
        b = int(b * 255)
        
        return f'#{r:02x}{g:02x}{b:02x}'
    
    @staticmethod
    def generate_color_with_variation(object_id: str, variation: int = 0) -> str:
        """
        Generate color with slight variation for related objects
        
        Args:
            object_id: Base object ID
            variation: Variation index for slight color shifts
            
        Returns:
            Hex color string
        """
        # Add variation to the ID before hashing
        modified_id = f"{object_id}_{variation}"
        return ColorGenerator.generate_color(modified_id)
    
    @staticmethod
    def get_contrasting_text_color(hex_color: str) -> str:
        """
        Get black or white text color for best contrast
        
        Args:
            hex_color: Background color in hex format
            
        Returns:
            '#000000' or '#FFFFFF' for best contrast
        """
        # Remove # if present
        hex_color = hex_color.lstrip('#')
        
        # Convert to RGB
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        
        # Calculate relative luminance
        # Using Web Content Accessibility Guidelines (WCAG) formula
        r_norm = r / 255.0
        g_norm = g / 255.0
        b_norm = b / 255.0
        
        # Apply gamma correction
        r_linear = r_norm / 12.92 if r_norm <= 0.03928 else ((r_norm + 0.055) / 1.055) ** 2.4
        g_linear = g_norm / 12.92 if g_norm <= 0.03928 else ((g_norm + 0.055) / 1.055) ** 2.4
        b_linear = b_norm / 12.92 if b_norm <= 0.03928 else ((b_norm + 0.055) / 1.055) ** 2.4
        
        # Calculate luminance
        luminance = 0.2126 * r_linear + 0.7152 * g_linear + 0.0722 * b_linear
        
        # Return white text for dark backgrounds, black for light
        return '#FFFFFF' if luminance < 0.5 else '#000000'
    
    @staticmethod
    def batch_generate_colors(object_ids: list, object_type: str = 'default') -> dict:
        """
        Generate colors for multiple objects at once
        
        Args:
            object_ids: List of object IDs
            object_type: Type of objects for color range adjustment
            
        Returns:
            Dictionary mapping IDs to hex colors
        """
        colors = {}
        for obj_id in object_ids:
            colors[obj_id] = ColorGenerator.generate_color(obj_id, object_type)
        return colors

# Global instance
color_generator = ColorGenerator()