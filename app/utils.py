from datetime import datetime
from django.http import JsonResponse
from shopify import ShopifyResource, Order
import logging
from urllib.parse import urlparse, parse_qs
import pandas as pd
from .models import Orders, OrderItems, ShopifyInventoryData, ShopifyCampaign
from django.db import transaction
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.parse
import requests
from .optimize import get_date_range, split_date_range, fetch_orders_for_interval
logger = logging.getLogger(__name__)

def get_store_name(store_url):
    stores = {
        "UK":['rdx-sports-store.myshopify.com'],
        "USA":['rdx-sports-store-usa.myshopify.com'],
        "CA":['rdx-sports-store-canada.myshopify.com'],
        "EU":['rdx-sports-store-europe.myshopify.com'],
        "Middle East":['rdx-sports-middle-east.myshopify.com'],
        "Global": ['rdx-sports-store-global.myshopify.com']
        }
    store_name = None
    for region, urls in stores.items():
        if store_url in urls:
            store_name = region
            break 
        
    return store_name

def extract_params(landing_site):
    parsed_url = urllib.parse.urlparse(landing_site)
    query_params = urllib.parse.parse_qs(parsed_url.query)

    keys_to_extract = ["cmp_id", "utm_campaign", "utm_source", "utm_medium", "utm_id", "campaign_id"]
    extracted_values = {key: query_params.get(key, [None])[0] for key in keys_to_extract}

    return extracted_values

def convert_to_shopify_date_format(date_str):
    try:
        if date_str.endswith("Z"):
            date_str = date_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(date_str)
        return dt.strftime('%Y-%m-%dT%H:%M:%S-00:00')
    except Exception as e:
        raise ValueError(f"Invalid date format: {e}")
    
# # fetches all records from Shopify
# def fetch_all_records(api_key, password, store_url, api_version, created_at_min=None, created_at_max=None):
#     shop_url = f"https://{api_key}:{password}@{store_url}/admin/api/{api_version}"
#     ShopifyResource.set_site(shop_url)

#     orders = []
#     limit = 250
#     #for fetching data
#     if created_at_max is None and created_at_min is None:
#         params = {
#             "limit": limit,
#             'status': 'any',
#         }
#     else:
#         params = {
#             "processed_at_min": created_at_min,
#             "processed_at_max": created_at_max,
#             "limit": limit,
#             'status': 'any',
#         }
    
#     current_orders = Order.find(**params)
#     while current_orders:
#         orders.extend(current_orders)
#         logger.info(f"Fetched {len(current_orders)} orders. Total so far: {len(orders)}.")

#         link_header = ShopifyResource.connection.response.headers.get("link")
#         if not link_header or 'rel="next"' not in link_header:
#             break

#         links = link_header.split(",")
#         next_link = next((link for link in links if 'rel="next"' in link), None)
#         if not next_link:
#             break

#         next_url = next_link.split(";")[0].strip("<> ")
#         parsed_url = urlparse(next_url)
#         page_info = parse_qs(parsed_url.query).get("page_info", [None])[0]
#         if not page_info:
#             break

#         params = {"page_info": page_info}
#         current_orders = Order.find(**params)

#     logger.info(f"Total orders fetched: {len(orders)}.")
#     return orders


# --- Main function to fetch all records, optimized for both cases.
def fetch_all_records(api_key, password, store_url, api_version, created_at_min=None, created_at_max=None):
    """
    Fetches all orders using concurrent interval-based fetching.
    """
    shop_url = f"https://{api_key}:{password}@{store_url}/admin/api/{api_version}"
    ShopifyResource.set_site(shop_url)

    # Determine overall date range if not provided
    if created_at_min is None or created_at_max is None:
        oldest_date, latest_date = get_date_range(api_key, password, store_url, api_version)
        if oldest_date is None or latest_date is None:
            logger.error("No orders found or unable to determine date range.")
            # print("No orders found or unable to determine date range.")
            return []
        # Use the discovered dates as the range
        created_at_min = oldest_date.isoformat() if isinstance(oldest_date, datetime) else oldest_date
        created_at_max = latest_date.isoformat() if isinstance(latest_date, datetime) else latest_date

    # Ensure we have datetime objects to split the range
    if isinstance(created_at_min, str):
        start_date = datetime.fromisoformat(created_at_min)
    else:
        start_date = created_at_min
    if isinstance(created_at_max, str):
        end_date = datetime.fromisoformat(created_at_max)
    else:
        end_date = created_at_max

    # Split the overall range into smaller intervals (adjust delta_days as needed)
    intervals = split_date_range(start_date, end_date, delta_days=1)
    logger.info(f"Splitting date range {start_date.isoformat()} to {end_date.isoformat()} into {len(intervals)} intervals.")
    # print(f"Splitting date range {start_date.isoformat()} to {end_date.isoformat()} into {len(intervals)} intervals.")

    all_orders = []
    # Limit concurrency to 2 workers to match Shopify's rate limit.
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_to_interval = {
            executor.submit(fetch_orders_for_interval, api_key, password, store_url, api_version, interval[0], interval[1]): interval
            for interval in intervals
        }
        for future in as_completed(future_to_interval):
            interval = future_to_interval[future]
            try:
                orders = future.result()
                all_orders.extend(orders)
                logger.info(f"Completed interval {interval} with {len(orders)} orders.")
                # print(f"Completed interval {interval} with {len(orders)} orders.")
            except Exception as e:
                logger.error(f"Error fetching interval {interval}: {e}")
                # print(f"Error fetching interval {interval}: {e}")

    logger.info(f"Total orders fetched: {len(all_orders)}")
    # print(f"Total orders fetched: {len(all_orders)}")
    return all_orders

# # processes the fetched records
# def process_shopify_records(orders, store_name):
#     if not orders:
#         return JsonResponse({'message': 'No orders found'}, status=404)
    
#     order_data = []
    
#     for order in orders:
#         try:
#             shipping_line = order.shipping_lines[0].title if order.shipping_lines else 'Not specified'
#             customer_name = f"{order.customer.first_name} {order.customer.last_name}" if order.customer else 'N/A'
#             destination = order.shipping_address.city if order.shipping_address else 'N/A'
#             shipping_address = (
#                 f"{order.shipping_address.name}, {order.shipping_address.address1}, "
#                 f"{order.shipping_address.city}, {order.shipping_address.province_code}, "
#                 f"{order.shipping_address.zip}, {order.shipping_address.country_code}"
#                 if order.shipping_address else 'N/A'
#                 )
#             billing_address = (
#                 f"{order.billing_address.name}, {order.billing_address.address1}, "
#                 f"{order.billing_address.city}, {order.billing_address.province_code}, "
#                 f"{order.billing_address.zip}, {order.billing_address.country_code}"
#                 if order.billing_address else 'N/A'
#             )
#             shipping_address_latitude = order.shipping_address.latitude
#             shipping_address_longitude = order.shipping_address.longitude
#             billing_address_latitude = order.billing_address.latitude
#             billing_address_longitude = order.billing_address.longitude
#             tracking_number = order.fulfillments[0].tracking_number if order.fulfillments else 'N/A'
#             discount_codes = (
#                 ", ".join([d.code for d in order.discount_codes]) if order.discount_codes else 'N/A'
#             )
#             payment_gateways = (
#                 ", ".join([pg for pg in order.payment_gateway_names]) if order.payment_gateway_names else 'N/A'
#             )
#             delivery_status = (
#                 order.fulfillments[0].shipment_status if order.fulfillments and len(order.fulfillments) > 0 else 'Not available'
#             )
#             status = (
#                 order.fulfillments[0].status if order.fulfillments and len(order.fulfillments) > 0 else 'Not available'
#             )
            
#             # Safely extract discounts
#             discount_codes = ", ".join([d.code for d in order.discount_codes]) if order.discount_codes else 'N/A'
#             discount_types = ", ".join([d.type for d in order.discount_codes]) if order.discount_codes else 'N/A'
#             discount_amount = ", ".join(f"{d.amount}" for d in order.discount_codes) if order.discount_codes else "0.00"
#             discount_currency = order.currency
            
#             # Safely calculate refunded amount
#             refunded_amount = sum(
#                 float(refund.transactions[0].amount or 0.00) for refund in order.refunds if refund.transactions
#             ) if order.refunds else 0.00
            
#             # Safely extract shipping price
#             shipping_price = float(order.shipping_lines[0].price or 0.00) if order.shipping_lines and len(order.shipping_lines) > 0 else 0.00
            
#             for item in order.line_items:
#                 print("shopify_created_at: ", order.created_at)
#                 order_data.append({
#                     "OrderID": order.name,
#                     "order_processed_at": order.processed_at,
#                     "order_created_at": order.created_at,
#                     'item_count': len(order.line_items),
#                     "shipping_price": shipping_price,
#                     "item_title": item.title,
#                     "item_sku": item.sku,
#                     "item_variant": item.variant_title,
#                     "item_quantity": item.quantity,
#                     "item_price": f"{float(item.price or 0.00):.2f} {order.currency}",
#                     "customer_name": customer_name,
#                     "shipping_address": shipping_address,
#                     "billing_address": billing_address,
#                     "delivery_method": shipping_line,
#                     "delivery_status": delivery_status,
#                     "discount_code": discount_codes,
#                     "discount_type": discount_types,
#                     "discount_amount": discount_amount,
#                     "total_discount_amount": f"{float(order.total_discounts or 0.00):.2f} {discount_currency}",
#                     "refunded_amount": f"{refunded_amount:.2f} {order.currency}",
#                     "total_paid": f"{float(order.total_price or 0.00):.2f} {order.currency}",
#                     "payment_status": order.financial_status,
#                     "fulfillment_status": order.fulfillment_status if order.fulfillment_status else "unfulfilled",
#                     "channel": order.source_name,
#                     "destination": destination,
#                     "tags": order.tags,
#                     "tracking_number": tracking_number,
#                     "status": status,
#                     "updated_at_shopify": order.updated_at,
#                     "store_name": store_name,
#                     "landing_site": order.landing_site,
#                     "order_status_url": order.order_status_url,
#                     "shipping_address_latitude": shipping_address_latitude,
#                     "shipping_address_longitude": shipping_address_longitude,
#                     "billing_address_latitude": billing_address_latitude,
#                     "billing_address_longitude": billing_address_longitude,
#                     "referring_site": order.referring_site,
#                     "payment_gateways": payment_gateways
#                 })                
#                 # order_data.update(extract_params(order["landing_site"]))
#                 # Extract parameters and update the last added order dictionary
#                 # order_data[-1].update(extract_params(order["landing_site"]))
#                 order_data[-1].update(extract_params(order.landing_site))


            
        
#         except Exception as e:
#             logger.error(f"Error processing order {order.id}: {e}")
#             continue
#     return order_data


def process_shopify_records(orders, store_name):
    if not orders:
        return JsonResponse({'message': 'No orders found'}, status=404)

    order_data = []

    for order in orders:
        try:
            # Extract key order details once (avoiding repetitive `if-else` checks)
            shipping_line = order.shipping_lines[0].title if order.shipping_lines else 'Not specified'
            customer_name = f"{order.customer.first_name} {order.customer.last_name}" if order.customer else 'N/A'
            destination = order.shipping_address.city if order.shipping_address else 'N/A'

            # shipping_address = (
            #     f"{order.shipping_address.name}, {order.shipping_address.address1}, "
            #     f"{order.shipping_address.city}, {order.shipping_address.province_code}, "
            #     f"{order.shipping_address.zip}, {order.shipping_address.country_code}"
            #     if order.shipping_address else 'N/A'
            # )
            # billing_address = (
            #     f"{order.billing_address.name}, {order.billing_address.address1}, "
            #     f"{order.billing_address.city}, {order.billing_address.province_code}, "
            #     f"{order.billing_address.zip}, {order.billing_address.country_code}"
            #     if order.billing_address else 'N/A'
            # )
            shipping_address_name = order.shipping_address.name if order.shipping_address else 'N/A'
            shipping_address_address1 = order.shipping_address.address1 if order.shipping_address else 'N/A'
            shipping_address_city = order.shipping_address.city if order.shipping_address else 'N/A'
            shipping_address_province_code = order.shipping_address.province_code if order.shipping_address else 'N/A'
            shipping_address_zip = order.shipping_address.zip if order.shipping_address else 'N/A'
            shipping_address_country_code = order.shipping_address.country_code if order.shipping_address else 'N/A'
            
            billing_address_name = order.billing_address.name if order.billing_address else 'N/A'
            billing_address_address1 = order.billing_address.address1 if order.billing_address else 'N/A'
            billing_address_city = order.billing_address.city if order.billing_address else 'N/A'
            billing_address_province_code = order.billing_address.province_code if order.billing_address else 'N/A'
            billing_address_zip = order.billing_address.zip if order.billing_address else 'N/A'
            billing_address_country_code = order.billing_address.country_code if order.billing_address else 'N/A'
            

            # Extract lat/long safely
            shipping_address_latitude = getattr(order.shipping_address, 'latitude', None)
            shipping_address_longitude = getattr(order.shipping_address, 'longitude', None)
            billing_address_latitude = getattr(order.billing_address, 'latitude', None)
            billing_address_longitude = getattr(order.billing_address, 'longitude', None)

            # Extract tracking and fulfillment details
            fulfillments = order.fulfillments or []
            tracking_number = fulfillments[0].tracking_number if fulfillments else 'N/A'
            delivery_status = fulfillments[0].shipment_status if fulfillments else 'Not available'
            fulfillment_status = fulfillments[0].status if fulfillments else 'Not available'

            # Extract discount details safely
            discount_codes = ", ".join(d.code for d in order.discount_codes) if order.discount_codes else 'N/A'
            discount_types = ", ".join(d.type for d in order.discount_codes) if order.discount_codes else 'N/A'
            discount_amount = ", ".join(f"{d.amount}" for d in order.discount_codes) if order.discount_codes else "0.00"

            # Compute refunded amount
            refunded_amount = sum(
                float(refund.transactions[0].amount or 0.00) 
                for refund in order.refunds if refund.transactions
            ) if order.refunds else 0.00

            # Compute shipping price safely
            shipping_price = float(order.shipping_lines[0].price or 0.00) if order.shipping_lines else 0.00

            # Iterate over line items
            for item in order.line_items:
                order_entry = {
                    "OrderID": order.name,
                    "order_processed_at": order.processed_at,
                    "order_created_at": order.created_at,
                    "item_count": len(order.line_items),
                    "shipping_price": shipping_price,
                    "item_title": item.title,
                    "item_sku": item.sku,
                    "item_variant": item.variant_title,
                    "item_quantity": item.quantity,
                    "item_price": f"{float(item.price or 0.00):.2f} {order.currency}",
                    "customer_name": customer_name,
                    "shipping_address_name": shipping_address_name,
                    "billing_address_name": billing_address_name,
                    "shipping_address_address1": shipping_address_address1,
                    "shipping_address_city": shipping_address_city,
                    "shipping_address_province_code": shipping_address_province_code,
                    "shipping_address_zip": shipping_address_zip,
                    "shipping_address_country_code": shipping_address_country_code,
                    "billing_address_address1": billing_address_address1,
                    "billing_address_city": billing_address_city,
                    "billing_address_province_code": billing_address_province_code,
                    "billing_address_zip": billing_address_zip,
                    "billing_address_country_code": billing_address_country_code,
                    "delivery_method": shipping_line,
                    "delivery_status": delivery_status,
                    "discount_code": discount_codes,
                    "discount_type": discount_types,
                    "discount_amount": discount_amount,
                    "total_discount_amount": f"{float(order.total_discounts or 0.00):.2f} {order.currency}",
                    "refunded_amount": f"{refunded_amount:.2f} {order.currency}",
                    "total_paid": f"{float(order.total_price or 0.00):.2f} {order.currency}",
                    "payment_status": order.financial_status,
                    "fulfillment_status": order.fulfillment_status if order.fulfillment_status else "unfulfilled",
                    "channel": order.source_name,
                    "destination": destination,
                    "tags": order.tags,
                    "tracking_number": tracking_number,
                    "status": fulfillment_status,
                    "updated_at_shopify": order.updated_at,
                    "store_name": store_name,
                    "landing_site": order.landing_site,
                    "order_status_url": order.order_status_url,
                    "shipping_address_latitude": shipping_address_latitude,
                    "shipping_address_longitude": shipping_address_longitude,
                    "billing_address_latitude": billing_address_latitude,
                    "billing_address_longitude": billing_address_longitude,
                    "referring_site": order.referring_site,
                    "payment_gateways": ", ".join(order.payment_gateway_names) if order.payment_gateway_names else 'N/A'
                }

                # Extract and update landing site parameters
                order_entry.update(extract_params(order.landing_site))

                order_data.append(order_entry)

        except Exception as e:
            logging.error(f"Error processing order {getattr(order, 'id', 'Unknown')}: {e}")

    return order_data

def get_model_fields(model):
    """
    Get all field names for a given Django model.
    """
    return [field.name for field in model._meta.fields]

# def save_order_data_to_db(order_data):
#     try:
#         with transaction.atomic():
#             logger.info("Order Transaction started...")

#             for order in order_data:
#                 # Check if the Customer exists
#                 customer, _ = Customer.objects.get_or_create(
#                     customer_name=order["customer_name"],
#                     shipping_address=order["shipping_address"],
#                     billing_address=order["billing_address"],
#                     shipping_address_latitude = order["shipping_address_latitude"],
#                     shipping_address_longitude = order["shipping_address_longitude"],
#                     billing_address_latitude = order["billing_address_latitude"],
#                     billing_address_longitude = order["billing_address_longitude"],
#                 )
#                 # Check if order already exists
#                 order_instance, created = Orders.objects.get_or_create(
#                     orderID=order["OrderID"],
#                     defaults={
#                         "customer": customer,  
#                         "order_processed_at": order.get("order_processed_at"),
#                         "order_created_at": order.get("order_created_at"),
#                         "item_count": order.get("item_count"),
#                         "shipping_price": order.get("shipping_price"),
#                         "delivery_method": order.get("delivery_method"),
#                         "delivery_status": order.get("delivery_status"),
#                         "discount_code": order.get("discount_code"),
#                         "discount_type": order.get("discount_type"),
#                         "discount_amount": order.get("discount_amount"),
#                         "total_discount_amount": order.get("total_discount_amount"),
#                         "refunded_amount": order.get("refunded_amount"),
#                         "total_paid": order.get("total_paid"),
#                         "payment_status": order.get("payment_status"),
#                         "fulfillment_status": order.get("fulfillment_status"),
#                         "channel": order.get("channel"),
#                         "destination": order.get("destination"),
#                         "tags": order.get("tags"),
#                         "tracking_number": order.get("tracking_number"),
#                         "status": order.get("status"),
#                         "updated_at_shopify": order.get("updated_at_shopify"),
#                         "store_name": order.get("store_name"),
                        
#                         "landing_site": order.get("landing_site"),
#                         "payment_gateway_names": order.get("payment_gateway_names"),
#                         "order_status_url": order.get("order_status_url"),
#                         "referring_site": order.get("referring_site"),
#                     },
#                 )

#                 if created:
#                     logger.info(f"New order created: {order_instance.orderID}")
#                 else:
#                     logger.info(f"Order already exists: {order_instance.orderID}")

#                 # OrderItems (Ensuring no duplicate items)
#                 order_item_exists = OrderItems.objects.filter(
#                     order=order_instance,
#                     item_title=order["item_title"],
#                     item_sku=order["item_sku"],
#                     item_variant=order["item_variant"],
#                 ).exists()

#                 if not order_item_exists:
#                     order_item = OrderItems.objects.create(
#                         order=order_instance,
#                         item_title=order["item_title"],
#                         item_sku=order["item_sku"],
#                         item_variant=order["item_variant"],
#                         item_quantity=order["item_quantity"],
#                         item_price=order["item_price"],
#                     )
#                     logger.info(f"Order item added: {order_item.item_title}")
#                 else:
#                     logger.info(f"Duplicate order item skipped: {order['item_title']}")
#                  # Shopify Campaigns
#                 campaign_exists = ShopifyCampaign.objects.filter(
#                     order=order_instance,
#                     shopif_order_id=order["OrderID"],
#                     landing_site=order["landing_site"],
#                     reffering_site=order["referring_site"]
#                 ).exists()

#                 if not campaign_exists:
#                     campaign = ShopifyCampaign.objects.create(
#                         order=order_instance,  
#                         cmp_id=order.get("cmp_id"),
#                         utm_campaign=order.get("utm_campaign"),
#                         utm_source=order.get("utm_source"),
#                         utm_medium=order.get("utm_medium"),
#                         shopif_order_id=order["OrderID"],
#                         landing_site=order.get("landing_site"),
#                         reffering_site=order.get("referring_site"),
#                     )
#                     logger.info(f"Campaign data added: {campaign.cmp_id}")
#                 else:
#                     logger.info(f"Duplicated campaign item skipped: {order.get('cmp_id')}")

#         logger.info("All orders successfully saved to the database.")

#     except Exception as e:
#         logger.error(f"Error saving Shopify orders: {e}")
#         raise


import logging
from django.db import transaction

logger = logging.getLogger(__name__)

def save_order_data_to_db(order_data):
    try:
        with transaction.atomic():
            logger.info("Starting order transaction...")

            # === STEP 1: Deduplicate Orders by orderID ===
            unique_orders_data = {}
            for order in order_data:
                order_id = order["OrderID"]
                if order_id not in unique_orders_data:
                    unique_orders_data[order_id] = order
                else:
                    logger.warning("Duplicate order in data skipped: %s", order_id)
            logger.info("Deduplication complete. %d unique orders found.", len(unique_orders_data))

            # === STEP 2: Cache Customers ===
            # customer_keys = {}
            # for order in unique_orders_data.values():
            #     key = (
            #         order["customer_name"],
            #         order["shipping_address_name"],
            #         order["billing_address_name"],
            #         order["shipping_address_address1"],
            #         order["shipping_address_city"],
            #         order["shipping_address_province_code"],
            #         order["shipping_address_zip"],
            #         order["shipping_address_country_code"],
            #         order["billing_address_address1"],
            #         order["billing_address_city"],
            #         order["billing_address_province_code"],
            #         order["billing_address_zip"],
            #         order["billing_address_country_code"],
            #         order["shipping_address_latitude"],
            #         order["shipping_address_longitude"],
            #         order["billing_address_latitude"],
            #         order["billing_address_longitude"],
                    
            #     )
            #     if key not in customer_keys:
            #         customer_keys[key] = order
            # logger.info("Found %d unique customers.", len(customer_keys))

            # customer_cache = {}
            # for key, order in customer_keys.items():
            #     customer, created = Customer.objects.get_or_create(
            #         customer_name=order["customer_name"],
            #         shipping_address_name=order["shipping_address_name"],
            #         billing_address_name=order["billing_address_name"],
            #         shipping_address_address1=order["shipping_address_address1"],
            #         shipping_address_city=order["shipping_address_city"],
            #         shipping_address_province_code=order["shipping_address_province_code"],
            #         shipping_address_zip=order["shipping_address_zip"],
            #         shipping_address_country_code=order["shipping_address_country_code"],
            #         billing_address_address1=order["billing_address_address1"],
            #         billing_address_city=order["billing_address_city"],
            #         billing_address_province_code=order["billing_address_province_code"],
            #         billing_address_zip=order["billing_address_zip"],
            #         billing_address_country_code=order["billing_address_country_code"],
            #         shipping_address_latitude=order["shipping_address_latitude"],
            #         shipping_address_longitude=order["shipping_address_longitude"],
            #         billing_address_latitude=order["billing_address_latitude"],
            #         billing_address_longitude=order["billing_address_longitude"],
            #     )
            #     customer_cache[key] = customer
            #     if created:
            #         logger.info("Created new customer: %s", customer.customer_name)
            #     else:
            #         logger.info("Found existing customer: %s", customer.customer_name)

            # === STEP 3: Process Orders ===
            order_ids = list(unique_orders_data.keys())
            existing_orders_qs = Orders.objects.filter(orderID__in=order_ids)
            existing_orders = {o.orderID: o for o in existing_orders_qs}
            logger.info("Found %d existing orders in the database.", len(existing_orders))

            orders_to_create = []
            order_mapping = {}  # Mapping from orderID to order instance (existing or new)
            for order_id, order in unique_orders_data.items():
                if order_id in existing_orders:
                    order_mapping[order_id] = existing_orders[order_id]
                    logger.info("Order already exists: %s", order_id)
                else:
                #     cust_key = (
                #         order["customer_name"],
                #         order["shipping_address_name"],
                #         order["billing_address_name"],
                #         order["shipping_address_address1"],
                #         order["shipping_address_city"],
                #         order["shipping_address_province_code"],
                #         order["shipping_address_zip"],
                #         order["shipping_address_country_code"],
                #         order["billing_address_address1"],
                #         order["billing_address_city"],
                #         order["billing_address_province_code"],
                #         order["billing_address_zip"],
                #         order["billing_address_country_code"],
                #         order["shipping_address_latitude"],
                #         order["shipping_address_longitude"],
                #         order["billing_address_latitude"],
                #         order["billing_address_longitude"],
                #     )
                #     customer = customer_cache[cust_key]
                    new_order = Orders(
                        orderID=order_id,
                        # customer=customer,
                        customer_name=order.get("customer_name"),
                        shipping_address_name=order.get("shipping_address_name"),
                        billing_address_name=order.get("billing_address_name"),
                        shipping_address_address1=order.get("shipping_address_address1"),
                        shipping_address_city=order.get("shipping_address_city"),
                        shipping_address_province_code=order.get("shipping_address_province_code"),
                        shipping_address_zip=order.get("shipping_address_zip"),
                        shipping_address_country_code=order.get("shipping_address_country_code"),
                        billing_address_address1=order.get("billing_address_address1"),
                        billing_address_city=order.get("billing_address_city"),
                        billing_address_province_code=order.get("billing_address_province_code"),
                        billing_address_zip=order.get("billing_address_zip"),
                        billing_address_country_code=order.get("billing_address_country_code"),
                        shipping_address_latitude=order.get("shipping_address_latitude"),
                        shipping_address_longitude=order.get("shipping_address_longitude"),
                        billing_address_latitude=order.get("billing_address_latitude"),
                        billing_address_longitude=order.get("billing_address_longitude"),
                        order_processed_at=order.get("order_processed_at"),
                        order_created_at=order.get("order_created_at"),
                        item_count=order.get("item_count"),
                        shipping_price=order.get("shipping_price"),
                        delivery_method=order.get("delivery_method"),
                        delivery_status=order.get("delivery_status"),
                        discount_code=order.get("discount_code"),
                        discount_type=order.get("discount_type"),
                        discount_amount=order.get("discount_amount"),
                        total_discount_amount=order.get("total_discount_amount"),
                        refunded_amount=order.get("refunded_amount"),
                        total_paid=order.get("total_paid"),
                        payment_status=order.get("payment_status"),
                        fulfillment_status=order.get("fulfillment_status"),
                        channel=order.get("channel"),
                        destination=order.get("destination"),
                        tags=order.get("tags"),
                        tracking_number=order.get("tracking_number"),
                        status=order.get("status"),
                        updated_at_shopify=order.get("updated_at_shopify"),
                        store_name=order.get("store_name"),
                        landing_site=order.get("landing_site"),
                        payment_gateway_names=order.get("payment_gateway_names"),
                        order_status_url=order.get("order_status_url"),
                        referring_site=order.get("referring_site"),
                    )
                    orders_to_create.append(new_order)
                    order_mapping[order_id] = new_order

            if orders_to_create:
                logger.info("Creating %d new orders.", len(orders_to_create))
                Orders.objects.bulk_create(orders_to_create)
                # Re-fetch the orders so that the instances have proper primary keys.
                saved_orders = Orders.objects.filter(orderID__in=order_ids)
                for order_obj in saved_orders:
                    order_mapping[order_obj.orderID] = order_obj
                logger.info("Re-fetched orders; order mapping updated with primary keys.")
            else:
                logger.info("No new orders to create.")

            # === STEP 4: Process OrderItems ===
            order_item_keys = set()
            existing_items_qs = OrderItems.objects.filter(order__orderID__in=order_ids)
            for item in existing_items_qs:
                key = (item.order.orderID, item.item_title, item.item_sku, item.item_variant)
                order_item_keys.add(key)
            logger.info("Found %d existing order items in the database.", len(order_item_keys))

            order_items_to_create = []
            # Iterate over the original data in case one order has multiple items.
            for order in order_data:
                key = (order["OrderID"], order["item_title"], order["item_sku"], order["item_variant"])
                if key not in order_item_keys:
                    order_instance = order_mapping.get(order["OrderID"])
                    if order_instance:
                        new_item = OrderItems(
                            order=order_instance,
                            item_title=order["item_title"],
                            item_sku=order["item_sku"],
                            item_variant=order["item_variant"],
                            item_quantity=order["item_quantity"],
                            item_price=order["item_price"],
                        )
                        order_items_to_create.append(new_item)
                        order_item_keys.add(key)
                        logger.info("Added order item: '%s' for order: %s", order["item_title"], order["OrderID"])
                else:
                    logger.warning("Duplicate order item skipped: '%s' for order: %s", order["item_title"], order["OrderID"])
            if order_items_to_create:
                logger.info("Creating %d new order items.", len(order_items_to_create))
                OrderItems.objects.bulk_create(order_items_to_create)
            else:
                logger.info("No new order items to create.")

            # === STEP 5: Process Shopify Campaigns ===
            campaign_keys = set()
            existing_campaigns_qs = ShopifyCampaign.objects.filter(order__orderID__in=order_ids)
            for camp in existing_campaigns_qs:
                key = (camp.order.orderID, camp.landing_site, camp.reffering_site)
                campaign_keys.add(key)
            logger.info("Found %d existing campaigns in the database.", len(campaign_keys))

            campaigns_to_create = []
            for order in order_data:
                key = (order["OrderID"], order["landing_site"], order["referring_site"])
                if key not in campaign_keys:
                    order_instance = order_mapping.get(order["OrderID"])
                    if order_instance:
                        new_campaign = ShopifyCampaign(
                            order=order_instance,
                            cmp_id=order.get("cmp_id"),
                            utm_id = order.get("utm_id"),
                            campaign_id = order.get("campaign_id"),
                            utm_campaign=order.get("utm_campaign"),
                            utm_source=order.get("utm_source"),
                            utm_medium=order.get("utm_medium"),
                            shopif_order_id=order["OrderID"],
                            landing_site=order.get("landing_site"),
                            reffering_site=order.get("referring_site"),
                        )
                        campaigns_to_create.append(new_campaign)
                        campaign_keys.add(key)
                        logger.info("Added campaign: '%s' for order: %s", new_campaign.cmp_id, order["OrderID"])
                else:
                    logger.warning("Duplicate campaign skipped: '%s' for order: %s", order.get("cmp_id"), order["OrderID"])
            if campaigns_to_create:
                logger.info("Creating %d new campaigns.", len(campaigns_to_create))
                ShopifyCampaign.objects.bulk_create(campaigns_to_create)
            else:
                logger.info("No new campaigns to create.")

            logger.info("All orders, order items, and campaigns successfully saved to the database.")

    except Exception as e:
        logger.error("Error saving Shopify orders: %s", e, exc_info=True)
        raise

    
def save_inventory_data_to_db(inventory_data):
    try:
        with transaction.atomic():
            logger.info("Inventory Transaction started...")

            for inventory_item in inventory_data:
                product_id = inventory_item.get("product_id")
                variant_id = inventory_item.get("variant_id")

                if not product_id or not variant_id:
                    logger.warning("Skipping entry due to missing product_id or variant_id")
                    continue

                inv_instance, created = ShopifyInventoryData.objects.update_or_create(
                    product_id=product_id, 
                    variant_id=variant_id,  
                    defaults={
                        "product_title": inventory_item.get("product_title"),
                        "vendor": inventory_item.get("vendor"),
                        "tags": inventory_item.get("tags"),
                        "product_type": inventory_item.get("product_type"),
                        "category": inventory_item.get("category"),
                        "category_name": inventory_item.get("category_name"),
                        "collections": inventory_item.get("collections"),
                        "variant_title": inventory_item.get("variant_title"),
                        "variant_sku": inventory_item.get("variant_sku"),
                        "location_id": inventory_item.get("location_id"),
                        "location_name": inventory_item.get("location_name"),
                        "available": inventory_item.get("available", 0),
                        "reserved": inventory_item.get("reserved", 0),
                        "incoming": inventory_item.get("incoming", 0),
                        "committed": inventory_item.get("committed", 0),
                        "damaged": inventory_item.get("damaged", 0),  
                        "on_hand": inventory_item.get("on_hand", 0),
                        "quality_control": inventory_item.get("quality_control", 0),
                        "safety_check": inventory_item.get("safety_check", 0),
                    },
                )

                if created:
                    logger.info(f"New inventory item created: {product_id} - {variant_id}")
                else:
                    logger.info(f"Inventory item updated: {product_id} - {variant_id}")

            logger.info("All inventory items successfully saved to the database.")

    except Exception as e:
        logger.error(f"Error saving Shopify inventory data: {e}")
        raise

def fetch_inventory_data(password, store_url, api_version, store_name):
    # --------------------------------------------------
    # Shopify API Configuration
    # --------------------------------------------------
    SHOPIFY_GRAPHQL_URL = f"https://{store_url}/admin/api/{api_version}/graphql.json"

    HEADERS = {
        "X-Shopify-Access-Token": password,
        "Content-Type": "application/json"
    }

    # --------------------------------------------------
    # Rate Limit / Throttle Settings
    # --------------------------------------------------
    MAX_QUERY_COST_THRESHOLD = 900    # Aim to stay below this
    SLEEP_BETWEEN_CALLS = 0.5         # Small delay between pages

    # All quantity fields we want as columns
    QUANTITY_FIELDS = [
        "available",
        "reserved",
        "incoming",
        "committed",
        "damaged",
        "on_hand",
        "quality_control",
        "safety_stock",
    ]
    has_next_page = True
    cursor = None
    variant_cursor = None
    collection_cursor = None
    category = "Uncategorized"  # 
    page_number = 1

    all_data = []  # Will store flattened rows
    while has_next_page:
        # ---------------------------------------------------
        # GraphQL Query
        # - Smaller 'first' to reduce cost
        # - Enough subfields to get inventory data
        # ---------------------------------------------------
        graphql_query = f"""
        {{
          products(first: 20 {f', after: "{cursor}"' if cursor else ''}) {{
            pageInfo {{
              hasNextPage
              endCursor
            }}
            edges {{
              node {{
                id
                title
                status
                vendor
                handle
                tags
                productType
                productCategory {{
                  productTaxonomyNode {{
                    fullName
                  }}
                }}
                collections(first: 30) {{
                  edges {{
                    node {{
                      title
                    }}
                  }}
                }}
                variants(first: 30) {{
                  edges {{
                    node {{
                      id
                      title
                      sku
                      inventoryItem {{
                        id
                        sku
                        inventoryLevels(first: 20) {{
                          edges {{
                            node {{
                              id
                              location {{
                                id
                                name
                              }}
                              quantities(
                                names: [
                                  "available",
                                  "reserved",
                                  "incoming",
                                  "committed",
                                  "damaged",
                                  "on_hand",
                                  "quality_control",
                                  "safety_stock"
                                ]
                              ) {{
                                name
                                quantity
                              }}
                            }}
                          }}
                        }}
                      }}
                    }}
                  }}
                }}
              }}
            }}
          }}
        }}
        """

        response = requests.post(
            SHOPIFY_GRAPHQL_URL,
            headers=HEADERS,
            json={"query": graphql_query}
        )

        if response.status_code == 200:
            data = response.json()
            # print(json.dumps(data, indent=2))


            # If GraphQL errors exist, print and break
            if "errors" in data:
                print("GraphQL Error:", data["errors"])
                break

            # ---------------------------------------------------
            # Optional: Check cost
            # ---------------------------------------------------
            cost_info = data.get("extensions", {}).get("cost")
            if cost_info:
                # print("Throttle Status:", json.dumps(cost_info, indent=2))
                requested_query_cost = cost_info.get("requestedQueryCost")
                actual_query_cost = cost_info.get("actualQueryCost")
                throttle_status = cost_info.get("throttleStatus", {})
                currently_available = throttle_status.get("currentlyAvailable")
                restore_rate = throttle_status.get("restoreRate")

                print(f"\n=== Page {page_number} ===")
                print(f"Requested Query Cost: {requested_query_cost}")
                print(f"Actual Query Cost: {actual_query_cost}")
                print(f"Currently Available: {currently_available}")
                print(f"Restore Rate: {restore_rate} points/sec")

                # If we might exceed available cost next time, wait
                if requested_query_cost and currently_available:
                    if requested_query_cost > currently_available:
                        time_to_wait = (requested_query_cost - currently_available) / restore_rate
                        time_to_wait += 2  # small buffer
                        print("WARNING: Next query might exceed available cost.")
                        print(f"Sleeping ~{time_to_wait:.2f} seconds to avoid throttle...")
                        time.sleep(time_to_wait)

                    elif requested_query_cost > MAX_QUERY_COST_THRESHOLD:
                        print("WARNING: Query cost is high. Consider lowering 'first:' values.")
            else:
                # If no cost info, just print a note
                print(f"\n=== Page {page_number} ===")
                print("No cost info returned.")

            # ---------------------------------------------------
            # Flatten the product data into rows
            # ---------------------------------------------------
            product_edges = data["data"]["products"]["edges"]
            for edge in product_edges:
                product = edge["node"]
                
                product_id = product["id"]
                product_title = product["title"]
                vendor = product["vendor"]
                tags = product["tags"]
                product_type = product["productType"]
                # print("Product:", product["title"], "Status:", product.get("status"))
                # print("Variants:", product.get("variants"))
                print("Product title: ", product_title)

                # Extract category (if any)
                # category = product.get('productCategory', {}).get('productTaxonomyNode', {}).get('fullName', 'Uncategorized')

                product_category = product.get("productCategory") or {}
                product_tax_node = product_category.get("productTaxonomyNode") or {}
                category = product_tax_node.get("fullName", "Uncategorized")
                category_name = category.split(">")[-1].strip()
                
                # -------------------------------
                # NEW: Extract collections data
                # -------------------------------
                collections_edges = product.get("collections", {}).get("edges", [])
                collections_list = [coll_edge["node"]["title"] for coll_edge in collections_edges]
                # Join multiple collection names with a semicolon.
                collections_str = ";".join(collections_list) if collections_list else ""


                variant_edges = product.get("variants", {}).get("edges", [])
                if not variant_edges:
                    # If no variants, create one "empty" row
                    row = {
                        "product_id": product_id,
                        "product_title": product_title,
                        "vendor": vendor,
                        "tags": tags,
                        "product_type": product_type,
                        "category": category,
                        "category_name": category_name,
                        "collections": collections_str,
                        "variant_id": None,
                        "variant_title": None,
                        "variant_sku": None,
                        "location_id": None,
                        "location_name": None,
                        "store_name": store_name,
                    }
                    # For each quantity field, store 0 or None (choose your preference)
                    for qf in QUANTITY_FIELDS:
                        row[qf] = 0
                    all_data.append(row)

                else:
                    for v_edge in variant_edges:
                        variant = v_edge["node"]
                        variant_id = variant["id"]
                        variant_title = variant["title"]
                        variant_sku = variant["sku"]
                        print("variant_id: ", variant_id)
                        print("variant_title: ", variant_title)
                        print("variant_sku: ", variant_sku)
                        

                        inventory_item = variant.get("inventoryItem")
                        if not inventory_item:
                            # No inventory item
                            row = {
                                "product_id": product_id,
                                "product_title": product_title,
                                "vendor": vendor,
                                "tags": tags,
                                "product_type": product_type,
                                "category": category,
                                "category_name": category_name,
                                "collections": collections_str,  
                                "variant_id": variant_id,
                                "variant_title": variant_title,
                                "variant_sku": variant_sku,
                                "location_id": None,
                                "location_name": None,
                                "store_name": store_name,
                                
                            }
                            for qf in QUANTITY_FIELDS:
                                row[qf] = 0
                            all_data.append(row)
                            continue

                        inv_levels = inventory_item.get("inventoryLevels", {}).get("edges", [])
                        if not inv_levels:
                            # No inventory levels
                            row = {
                                "product_id": product_id,
                                "product_title": product_title,
                                "vendor": vendor,
                                "tags": tags,
                                "product_type": product_type,
                                "category": category,
                                "category_name": category_name,
                                "collections": collections_str,  
                                "variant_id": variant_id,
                                "variant_title": variant_title,
                                "variant_sku": variant_sku,
                                "location_id": None,
                                "location_name": None,
                                "store_name": store_name,
                                
                            }
                            for qf in QUANTITY_FIELDS:
                                row[qf] = 0
                            all_data.append(row)
                            continue

                        # Build a row for each location
                        for lvl_edge in inv_levels:
                            node_lvl = lvl_edge["node"]
                            location_data = node_lvl["location"]
                            location_id = location_data["id"]
                            location_name = location_data["name"]

                            # Initialize a row for (product-variant-location)
                            row = {
                                "product_id": product_id,
                                "product_title": product_title,
                                "vendor": vendor,
                                "tags": tags,
                                "product_type": product_type,
                                "category": category,
                                "category_name": category_name,
                                "collections": collections_str,  
                                "variant_id": variant_id,
                                "variant_title": variant_title,
                                "variant_sku": variant_sku,
                                "location_id": location_id,
                                "location_name": location_name,
                                "store_name": store_name,
                                
                            }

                            # Initialize all quantity columns to 0
                            for qf in QUANTITY_FIELDS:
                                row[qf] = 0

                            # Overwrite with actual quantities returned
                            for qty_obj in node_lvl.get("quantities", []):
                                qty_name = qty_obj["name"]
                                qty_val = qty_obj["quantity"]
                                # If the API returns a name that is in QUANTITY_FIELDS, set it
                                if qty_name in QUANTITY_FIELDS:
                                    row[qty_name] = qty_val
                                print("quantity_name: ", qty_name)
                                print("quantity_val: ", qty_val)

                            # Now we have one row for this location
                            all_data.append(row)

            # ---------------------------------------------------
            # Update pagination
            # ---------------------------------------------------
            page_info = data["data"]["products"]["pageInfo"]
            has_next_page = page_info["hasNextPage"]
            cursor = page_info["endCursor"]
            page_number += 1

            # Optional short delay between pages
            time.sleep(SLEEP_BETWEEN_CALLS)

        else:
            print(f"HTTP Error {response.status_code}: {response.text}")
            break
        
    # df = pd.DataFrame(all_data)
    # print(df.head())
    # df.to_csv("productsss.csv", encoding='utf-8')
    return all_data



