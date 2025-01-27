import logging
import pandas as pd
import zipfile
from io import BytesIO
from django.http import JsonResponse, HttpResponse
from rest_framework.decorators import api_view
from shopify import ShopifyResource, Order
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from django.db import transaction

from .models import SecretSurprise, ShopifyOrders

from .serializers import SecretSurpriseSerializer, ShopifyOrdersSerializer
from rest_framework import serializers
logger = logging.getLogger(__name__)

def convert_to_shopify_date(date_str):
    try:
        if date_str.endswith("Z"):
            date_str = date_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(date_str)
        return dt.strftime('%Y-%m-%dT%H:%M:%S-00:00')
    except Exception as e:
        raise ValueError(f"Invalid date format: {e}")

def fetch_all_orders(api_key, password, store_url, api_version, created_at_min, created_at_max):
    shop_url = f"https://{api_key}:{password}@{store_url}/admin/api/{api_version}"
    ShopifyResource.set_site(shop_url)

    orders = []
    limit = 250
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

@api_view(['POST'])
def download_data(request):
    try:
        data = request.data
        api_key = data.get('api_key')
        password = data.get('password')
        store_url = data.get('store_url')
        api_version = data.get('api_version')
        created_at_min = data.get('created_at_min')
        created_at_max = data.get('created_at_max')

        if not all([api_key, password, store_url, api_version, created_at_min, created_at_max]):
            return JsonResponse({'error': 'Missing required fields'}, status=400)

        try:
            created_at_min = convert_to_shopify_date(created_at_min)
            created_at_max = convert_to_shopify_date(created_at_max)
        except ValueError as e:
            return JsonResponse({'error': str(e)}, status=400)

        if created_at_min > created_at_max:
            return JsonResponse({'error': 'Start date cannot be after the end date.'}, status=400)

        orders = fetch_all_orders(api_key, password, store_url, api_version, created_at_min, created_at_max)

        if not orders:
            return JsonResponse({'message': 'No orders found'}, status=404)

        normalized_data = []
        secret_surprise_data = []

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
                    if item.title == "Secret Surprise":
                        secret_surprise_data.append({
                            "order_id": order.name,
                            "item_title": item.title,
                            "item_price": f"{float(item.price or 0.00):.2f} {order.currency}",
                        })
                    else:
                        normalized_data.append({
                            "order_id": order.name,
                            "order_date": pd.to_datetime(order.created_at),
                            'item_count': len(order.line_items),
                            "item_title": item.title,
                            "item_sku": item.sku,
                            "item_variant": item.variant_title,
                            "item_quantity": item.quantity,
                            "item_price": f"{float(item.price or 0.00):.2f} {order.currency}",
                            "shipping_price": shipping_price,
                            "delivery_method": shipping_line,
                            "delivery_status": delivery_status,
                            "discount_code": discount_codes,
                            "discount_type": discount_types,
                            "discount_amount": discount_amount,
                            "total_discount_amount": f"{float(order.total_discounts or 0.00):.2f} {discount_currency}",
                            "refunded_amount": f"{refunded_amount:.2f} {order.currency}",
                            "total_paid": f"{float(order.total_price or 0.00):.2f} {order.currency}",
                            "payment_status": order.financial_status,
                            "fulfillment_status": order.fulfillment_status,
                            "channel": order.source_name,
                            "destination": destination,
                            "tags": order.tags,
                            "customer_name": customer_name,
                            "shipping_address": shipping_address,
                            "billing_address": billing_address,
                            "tracking_number": tracking_number,
                            "status": status,
                        })
            except Exception as e:
                logger.warning(f"Error processing order {order.id}: {e}")
                continue
        
        # response = save_data_to_csv(normalized_data, secret_surprise_data)
        # return response
        save_data_to_db(normalized_data, secret_surprise_data)
        
        return JsonResponse({'message': 'Data successfully saved to the database.'}, status=200)
        

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


def save_data_to_db(normalized_data, secret_surprise_data):
    try:
        # Save Shopify Orders
        shopify_orders_to_create = []
        existing_orders = set(
            ShopifyOrders.objects.values_list("order_id", "item_title", "item_sku")
        )  # Fetch existing (order_id, item_title, item_sku) tuples
        for order in normalized_data:
            key = (order["order_id"], order["item_title"], order["item_sku"])
            if key not in existing_orders:
                shopify_orders_to_create.append(ShopifyOrders(**order))

        if shopify_orders_to_create:
            ShopifyOrders.objects.bulk_create(shopify_orders_to_create, ignore_conflicts=True)
            logger.info(f"{len(shopify_orders_to_create)} new Shopify orders successfully saved to the database.")
        else:
            logger.info("No new Shopify orders to save.")
    except Exception as e:
        logger.error(f"Error saving Shopify orders to the database: {e}")
        raise

    try:
        # Save Secret Surprise Orders
        secret_surprises_to_create = []
        existing_secret_orders = set(
            SecretSurprise.objects.values_list("order_id", "item_title")
        )  # Fetch existing (order_id, item_title) tuples
        for secret_order in secret_surprise_data:
            key = (secret_order["order_id"], secret_order["item_title"])
            if key not in existing_secret_orders:
                secret_surprises_to_create.append(SecretSurprise(**secret_order))

        if secret_surprises_to_create:
            SecretSurprise.objects.bulk_create(secret_surprises_to_create, ignore_conflicts=True)
            logger.info(f"{len(secret_surprises_to_create)} new Secret Surprise orders successfully saved to the database.")
        else:
            logger.info("No new Secret Surprise orders to save.")
    except Exception as e:
        logger.error(f"Error saving Secret Surprise orders to the database: {e}")
        raise



def save_data_to_csv(normalized_data, secret_surprise_data):
    df = pd.DataFrame(normalized_data)
    df2 = pd.DataFrame(secret_surprise_data)
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr('orders.csv', df.to_csv(index=False))
        zip_file.writestr('secret_surprise_orders.csv', df2.to_csv(index=False))
    zip_buffer.seek(0)
    response = HttpResponse(zip_buffer, content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename=orders_data.zip'
    return response