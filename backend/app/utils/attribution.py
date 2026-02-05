"""
Attribution utilities for extracting tracking codes from BigCommerce orders.
"""

import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Tracking code patterns to search for
TRACKING_PATTERNS = [
    r"aff[_-]?code[=:]?\s*([A-Za-z0-9_-]+)",
    r"ref[=:]?\s*([A-Za-z0-9_-]+)",
    r"tracking[_-]?code[=:]?\s*([A-Za-z0-9_-]+)",
    r"utm_source[=:]?\s*([A-Za-z0-9_-]+)",
]


def extract_tracking_code(order_data: dict) -> Optional[str]:
    """
    Extract affiliate tracking code from BigCommerce order data.

    Searches in order of priority:
    1. Order custom fields
    2. Order staff notes (internal)
    3. Customer notes
    4. Order metadata
    5. Cart/form field data
    6. Referrer URL parameters

    Args:
        order_data: BigCommerce order webhook payload

    Returns:
        Tracking code string or None if not found
    """
    # 1. Check custom fields
    tracking_code = _extract_from_custom_fields(order_data)
    if tracking_code:
        logger.debug(f"Found tracking code in custom fields: {tracking_code}")
        return tracking_code

    # 2. Check staff notes
    tracking_code = _extract_from_notes(order_data.get("staff_notes", ""))
    if tracking_code:
        logger.debug(f"Found tracking code in staff notes: {tracking_code}")
        return tracking_code

    # 3. Check customer notes/message
    tracking_code = _extract_from_notes(order_data.get("customer_message", ""))
    if tracking_code:
        logger.debug(f"Found tracking code in customer message: {tracking_code}")
        return tracking_code

    # 4. Check order metadata
    tracking_code = _extract_from_metadata(order_data)
    if tracking_code:
        logger.debug(f"Found tracking code in metadata: {tracking_code}")
        return tracking_code

    # 5. Check form fields
    tracking_code = _extract_from_form_fields(order_data)
    if tracking_code:
        logger.debug(f"Found tracking code in form fields: {tracking_code}")
        return tracking_code

    # 6. Check referring URL
    external_source = order_data.get("external_source")
    if external_source:
        tracking_code = _extract_from_url(external_source)
        if tracking_code:
            logger.debug(f"Found tracking code in external source: {tracking_code}")
            return tracking_code

    logger.debug("No tracking code found in order data")
    return None


def _extract_from_custom_fields(order_data: dict) -> Optional[str]:
    """Extract tracking code from custom fields."""
    # BigCommerce custom fields in order
    custom_fields = order_data.get("custom_fields", [])

    for field in custom_fields:
        field_name = field.get("name", "").lower()
        if any(key in field_name for key in ["tracking", "affiliate", "ref", "aff_code"]):
            value = field.get("value")
            if value:
                return str(value).strip()

    return None


def _extract_from_notes(notes: str) -> Optional[str]:
    """Extract tracking code from notes using regex patterns."""
    if not notes:
        return None

    for pattern in TRACKING_PATTERNS:
        match = re.search(pattern, notes, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    return None


def _extract_from_metadata(order_data: dict) -> Optional[str]:
    """Extract tracking code from order metadata."""
    # Check various metadata locations
    metadata = order_data.get("metadata", {})
    if isinstance(metadata, dict):
        for key in ["tracking_code", "affiliate_code", "ref", "aff_code"]:
            if key in metadata:
                return str(metadata[key]).strip()

    return None


def _extract_from_form_fields(order_data: dict) -> Optional[str]:
    """Extract tracking code from order form fields."""
    form_fields = order_data.get("form_fields", [])

    for field in form_fields:
        field_name = field.get("name", "").lower()
        if any(key in field_name for key in ["tracking", "affiliate", "ref"]):
            value = field.get("value")
            if value:
                return str(value).strip()

    return None


def _extract_from_url(url: str) -> Optional[str]:
    """Extract tracking code from URL parameters."""
    if not url:
        return None

    from urllib.parse import urlparse, parse_qs

    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        # Check common affiliate parameter names
        for param in ["ref", "aff", "tracking", "affiliate", "utm_source", "via"]:
            if param in params:
                return params[param][0].strip()
    except Exception as e:
        logger.warning(f"Error parsing URL for tracking code: {e}")

    return None


def extract_order_line_items(order_data: dict) -> List[Dict]:
    """
    Extract line items from BigCommerce order data.

    Args:
        order_data: BigCommerce order data

    Returns:
        List of simplified line item dictionaries
    """
    items = []

    # BigCommerce sends products in order
    for item in order_data.get("products", []):
        items.append({
            "product_id": item.get("product_id"),
            "variant_id": item.get("variant_id"),
            "name": item.get("name"),
            "sku": item.get("sku"),
            "quantity": item.get("quantity"),
            "price": float(item.get("price_inc_tax", 0)),
            "total": float(item.get("total_inc_tax", 0)),
        })

    return items


def get_order_total(order_data: dict) -> float:
    """
    Get the order total value.

    Args:
        order_data: BigCommerce order data

    Returns:
        Order total as float
    """
    # Try total_inc_tax first, then total_ex_tax, then subtotal
    total = order_data.get("total_inc_tax")
    if total is None:
        total = order_data.get("total_ex_tax")
    if total is None:
        total = order_data.get("subtotal_inc_tax")
    if total is None:
        total = order_data.get("subtotal_ex_tax", 0)

    return float(total)


def get_order_subtotal(order_data: dict) -> float:
    """
    Get the order subtotal (before shipping/tax).

    Args:
        order_data: BigCommerce order data

    Returns:
        Order subtotal as float
    """
    subtotal = order_data.get("subtotal_inc_tax")
    if subtotal is None:
        subtotal = order_data.get("subtotal_ex_tax", 0)

    return float(subtotal)
