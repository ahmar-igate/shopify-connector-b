from datetime import datetime, timedelta
from django.http import JsonResponse
from shopify import ShopifyResource, Order
import logging
from urllib.parse import urlparse, parse_qs
import time

logger = logging.getLogger(__name__)


    
# --- Helper to split a date range into smaller intervals (e.g. daily chunks)
def split_date_range(start_date, end_date, delta_days=1):
    """
    Splits [start_date, end_date] into intervals of delta_days.
    Returns a list of (chunk_start, chunk_end) tuples as ISO strings.
    """
    intervals = []
    current_start = start_date
    while current_start < end_date:
        current_end = min(current_start + timedelta(days=delta_days), end_date)
        intervals.append((current_start.isoformat(), current_end.isoformat()))
        current_start = current_end
    return intervals

# --- Helper to determine the overall order date range when none is provided.
def get_date_range(api_key, password, store_url, api_version):
    """
    Determines the oldest and newest order dates by doing two lightweight API calls.
    """
    shop_url = f"https://{api_key}:{password}@{store_url}/admin/api/{api_version}"
    ShopifyResource.set_site(shop_url)

    # Get the most recent order
    params_latest = {"limit": 1, "status": "any"}
    latest_orders = Order.find(**params_latest)
    if not latest_orders:
        return None, None
    latest_date = latest_orders[0].created_at

    # Get the oldest order
    params_oldest = {"limit": 1, "status": "any", "order": "created_at asc"}
    oldest_orders = Order.find(**params_oldest)
    if not oldest_orders:
        return None, None
    oldest_date = oldest_orders[0].created_at

    return oldest_date, latest_date

# --- Function to fetch orders for a given date interval.
def fetch_orders_for_interval(api_key, password, store_url, api_version, created_at_min, created_at_max):
    """
    Fetches all orders between created_at_min and created_at_max (ISO8601 strings)
    by following paginated results.
    """
    orders = []
    limit = 250
    params = {
        "processed_at_min": created_at_min,
        "processed_at_max": created_at_max,
        "limit": limit,
        "status": "any",
    }
    current_orders = Order.find(**params)

    while current_orders:
        orders.extend(current_orders)
        logger.info(f"Fetched {len(current_orders)} orders for interval {created_at_min} to {created_at_max}. Total so far: {len(orders)}")
        # print(f"Fetched {len(current_orders)} orders for interval {created_at_min} to {created_at_max}. Total so far: {len(orders)}")

        # Check for a next page via the Link header
        link_header = ShopifyResource.connection.response.headers.get("link")
        if not link_header or 'rel="next"' not in link_header:
            break

        # Extract page_info from the next link
        links = link_header.split(",")
        next_link = next((link for link in links if 'rel="next"' in link), None)
        if not next_link:
            break

        next_url = next_link.split(";")[0].strip("<> ")
        parsed_url = urlparse(next_url)
        page_info = parse_qs(parsed_url.query).get("page_info", [None])[0]
        if not page_info:
            break

        # Prepare for the next page call
        params = {"page_info": page_info}
        current_orders = Order.find(**params)

        # Enforce a short delay to remain within Shopify’s rate limit.
        time.sleep(0.5)

    return orders


