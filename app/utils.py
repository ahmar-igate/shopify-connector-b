from datetime import datetime
from django.http import JsonResponse
from shopify import ShopifyResource, Order
import logging
from urllib.parse import urlparse, parse_qs
import pandas as pd
from .models import Orders, OrderItems, Customer
from django.db import transaction

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

def convert_to_shopify_date_format(date_str):
    try:
        if date_str.endswith("Z"):
            date_str = date_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(date_str)
        return dt.strftime('%Y-%m-%dT%H:%M:%S-00:00')
    except Exception as e:
        raise ValueError(f"Invalid date format: {e}")
    
# fetches all records from Shopify
def fetch_all_records(api_key, password, store_url, api_version, created_at_min=None, created_at_max=None):
    shop_url = f"https://{api_key}:{password}@{store_url}/admin/api/{api_version}"
    ShopifyResource.set_site(shop_url)

    orders = []
    limit = 250
    #for fetching data
    if created_at_max is None and created_at_min is None:
        params = {
            "limit": limit,
        }
    else:
        params = {
            "created_at_min": created_at_min,
            "created_at_max": created_at_max,
            "limit": limit,
        }
    
    current_orders = Order.find(**params)
    while current_orders:
        orders.extend(current_orders)
        logger.info(f"Fetched {len(current_orders)} orders. Total so far: {len(orders)}.")

        link_header = ShopifyResource.connection.response.headers.get("link")
        if not link_header or 'rel="next"' not in link_header:
            break

        links = link_header.split(",")
        next_link = next((link for link in links if 'rel="next"' in link), None)
        if not next_link:
            break

        next_url = next_link.split(";")[0].strip("<> ")
        parsed_url = urlparse(next_url)
        page_info = parse_qs(parsed_url.query).get("page_info", [None])[0]
        if not page_info:
            break

        params = {"page_info": page_info}
        current_orders = Order.find(**params)

    logger.info(f"Total orders fetched: {len(orders)}.")
    return orders

# processes the fetched records
def process_shopify_records(orders, store_name):
    if not orders:
        return JsonResponse({'message': 'No orders found'}, status=404)
    
    order_data = []
    
    for order in orders:
        try:
            shipping_line = order.shipping_lines[0].title if order.shipping_lines else 'Not specified'
            customer_name = f"{order.customer.first_name} {order.customer.last_name}" if order.customer else 'N/A'
            destination = order.shipping_address.city if order.shipping_address else 'N/A'
            shipping_address = (
                f"{order.shipping_address.name}, {order.shipping_address.address1}, "
                f"{order.shipping_address.city}, {order.shipping_address.province_code}, "
                f"{order.shipping_address.zip}, {order.shipping_address.country_code}"
                if order.shipping_address else 'N/A'
                )
            billing_address = (
                f"{order.billing_address.name}, {order.billing_address.address1}, "
                f"{order.billing_address.city}, {order.billing_address.province_code}, "
                f"{order.billing_address.zip}, {order.billing_address.country_code}"
                if order.billing_address else 'N/A'
            )
            tracking_number = order.fulfillments[0].tracking_number if order.fulfillments else 'N/A'
            discount_codes = (
                ", ".join([d.code for d in order.discount_codes]) if order.discount_codes else 'N/A'
            )
            delivery_status = (
                order.fulfillments[0].shipment_status if order.fulfillments and len(order.fulfillments) > 0 else 'Not available'
            )
            status = (
                order.fulfillments[0].status if order.fulfillments and len(order.fulfillments) > 0 else 'Not available'
            )
            
            # Safely extract discounts
            discount_codes = ", ".join([d.code for d in order.discount_codes]) if order.discount_codes else 'N/A'
            discount_types = ", ".join([d.type for d in order.discount_codes]) if order.discount_codes else 'N/A'
            discount_amount = ", ".join(f"{d.amount}" for d in order.discount_codes) if order.discount_codes else "0.00"
            discount_currency = order.currency
            
            # Safely calculate refunded amount
            refunded_amount = sum(
                float(refund.transactions[0].amount or 0.00) for refund in order.refunds if refund.transactions
            ) if order.refunds else 0.00
            
            # Safely extract shipping price
            shipping_price = float(order.shipping_lines[0].price or 0.00) if order.shipping_lines and len(order.shipping_lines) > 0 else 0.00
            
            for item in order.line_items:
                print("shopify_created_at: ", order.created_at)
                order_data.append({
                    "OrderID": order.name,
                    "order_date": order.created_at,
                    'item_count': len(order.line_items),
                    "shipping_price": shipping_price,
                    "item_title": item.title,
                    "item_sku": item.sku,
                    "item_variant": item.variant_title,
                    "item_quantity": item.quantity,
                    "item_price": f"{float(item.price or 0.00):.2f} {order.currency}",
                    "customer_name": customer_name,
                    "shipping_address": shipping_address,
                    "billing_address": billing_address,
                    "delivery_method": shipping_line,
                    "delivery_status": delivery_status,
                    "discount_code": discount_codes,
                    "discount_type": discount_types,
                    "discount_amount": discount_amount,
                    "total_discount_amount": f"{float(order.total_discounts or 0.00):.2f} {discount_currency}",
                    "refunded_amount": f"{refunded_amount:.2f} {order.currency}",
                    "total_paid": f"{float(order.total_price or 0.00):.2f} {order.currency}",
                    "payment_status": order.financial_status,
                    "fulfillment_status": order.fulfillment_status if order.fulfillment_status else "unfulfilled",
                    "channel": order.source_name,
                    "destination": destination,
                    "tags": order.tags,
                    "tracking_number": tracking_number,
                    "status": status,
                    "updated_at_shopify": order.updated_at,
                    "store_name": store_name,
                })                
            
           
        except Exception as e:
            logger.error(f"Error processing order {order.id}: {e}")
            continue
    return order_data

def get_model_fields(model):
    """
    Get all field names for a given Django model.
    """
    return [field.name for field in model._meta.fields]

def save_data_to_db(order_data):
    try:
        with transaction.atomic():
            logger.info("Transaction started...")

            for order in order_data:
                # Check if the Customer exists
                customer, _ = Customer.objects.get_or_create(
                    customer_name=order["customer_name"],
                    shipping_address=order["shipping_address"],
                    billing_address=order["billing_address"]
                )
                # Check if order already exists
                order_instance, created = Orders.objects.get_or_create(
                    orderID=order["OrderID"],
                    defaults={
                        "customer": customer,  # Now correctly assigned
                        "order_date": order.get("order_date"),
                        "item_count": order.get("item_count"),
                        "shipping_price": order.get("shipping_price"),
                        "delivery_method": order.get("delivery_method"),
                        "delivery_status": order.get("delivery_status"),
                        "discount_code": order.get("discount_code"),
                        "discount_type": order.get("discount_type"),
                        "discount_amount": order.get("discount_amount"),
                        "total_discount_amount": order.get("total_discount_amount"),
                        "refunded_amount": order.get("refunded_amount"),
                        "total_paid": order.get("total_paid"),
                        "payment_status": order.get("payment_status"),
                        "fulfillment_status": order.get("fulfillment_status"),
                        "channel": order.get("channel"),
                        "destination": order.get("destination"),
                        "tags": order.get("tags"),
                        "tracking_number": order.get("tracking_number"),
                        "status": order.get("status"),
                        "updated_at_shopify": order.get("updated_at_shopify"),
                        "store_name": order.get("store_name"),
                    },
                )

                if created:
                    logger.info(f"New order created: {order_instance.orderID}")
                else:
                    logger.info(f"Order already exists: {order_instance.orderID}")

                # OrderItems (Ensuring no duplicate items)
                order_item_exists = OrderItems.objects.filter(
                    order=order_instance,
                    item_title=order["item_title"],
                    item_sku=order["item_sku"],
                    item_variant=order["item_variant"],
                ).exists()

                if not order_item_exists:
                    order_item = OrderItems.objects.create(
                        order=order_instance,
                        item_title=order["item_title"],
                        item_sku=order["item_sku"],
                        item_variant=order["item_variant"],
                        item_quantity=order["item_quantity"],
                        item_price=order["item_price"],
                    )
                    logger.info(f"Order item added: {order_item.item_title}")
                else:
                    logger.info(f"Duplicate order item skipped: {order['item_title']}")

        logger.info("All orders successfully saved to the database.")

    except Exception as e:
        logger.error(f"Error saving Shopify orders: {e}")
        raise
        