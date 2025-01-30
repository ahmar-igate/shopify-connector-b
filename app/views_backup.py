import logging
from django.utils import timezone
import pandas as pd
import zipfile
from io import BytesIO
from django.http import JsonResponse, HttpResponse
from rest_framework.decorators import api_view
from shopify import ShopifyResource, Order
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from datetime import timedelta
from django.db import transaction

from .models_backup import SecretSurprise, ShopifyOrders, testOrders
from django.db.models import Min, Max

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
    #for fetching data
    params = {
        "created_at_min": created_at_min,
        "created_at_max": created_at_max,
        "limit": limit,
    }
        #Todo: 
        # - set created at min & created at max at according to db
        # - add shop region
        # - add option for fetching and syncing data of more stores


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

def get_shopify_data(orders):
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
                        "updated_at_shopify": order.updated_at,
                    })
        except Exception as e:
            logger.warning(f"Error processing order {order.id}: {e}")
            continue
    return normalized_data, secret_surprise_data

@api_view(['POST'])
def fetch_data(request):
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
        normalized_data, secret_surprise_data = get_shopify_data(orders)
            
        
        # response = save_data_to_csv(normalized_data, secret_surprise_data)
        # return response
        save_data_to_db(normalized_data, secret_surprise_data)
        
        return JsonResponse({'message': 'Data successfully saved to the database.'}, status=200)
        

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return JsonResponse({'error': str(e)}, status=500)

from datetime import datetime
from django.utils.dateparse import parse_datetime
@api_view(['POST'])
def sync_data(request):
    """
    Sync Shopify data with the database by updating matching records and adding new ones.
    """
    data = request.data
    api_key = data.get('api_key')
    password = data.get('password')
    store_url = data.get('store_url')
    api_version = data.get('api_version')

    if not all([api_key, password, store_url, api_version]):
        return JsonResponse({'error': 'Missing required fields'}, status=400)
    
    # Set the Shopify API URL
    shop_url = f"https://{api_key}:{password}@{store_url}/admin/api/{api_version}"
    ShopifyResource.set_site(shop_url)

    # Get the most recent `created_at` date in the database
    created_at_range = ShopifyOrders.objects.aggregate(
        created_at_max=Max('created_at')
    )

    created_at_max = created_at_range['created_at_max']
    if created_at_max:
        min_date = created_at_max - timedelta(days=60)
        max_date = created_at_max

        # Fetch existing records for comparison
        existing_orders = ShopifyOrders.objects.filter(
            created_at__gte=min_date,
            created_at__lte=max_date
        ).values('order_id', 'updated_at', 'id')  # Fetch `id`, `order_id`, and `updated_at`

        # Convert existing orders to a dictionary for quick lookup
        existing_orders_dict = {
            order['order_id']: {'updated_at': order['updated_at'], 'id': order['id']}
            for order in existing_orders
        }

        # Fetch orders from Shopify API within the same date range
        params = {
            "created_at_min": min_date,
            "created_at_max": max_date,
            "limit": 250,
        }
        current_orders = Order.find(**params)

        orders = []
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


        # Prepare records for update and create
        records_to_update = []
        records_to_create = []
        for order in orders:
            shopify_updated_at = parse_datetime(order.updated_at)
            order_id = order.name

            if shopify_updated_at is None:
                logger.warning(f"Invalid updated_at for order_id {order_id}. Skipping.")
                continue

            if order_id in existing_orders_dict:
                # If the record exists and needs updating
                existing_record = existing_orders_dict[order_id]
                if shopify_updated_at > existing_record['updated_at']:
                    records_to_update.append(
                        ShopifyOrders(
                            id=existing_record['id'],  # Include ID for bulk_update
                            order_id=order_id,
                            updated_at=shopify_updated_at,
                            item_title=order.line_items[0].title if order.line_items else "N/A",
                            item_sku=order.line_items[0].sku if order.line_items else "N/A",
                            total_paid=order.total_price
                        )
                    )
            else:
                # If the record doesn't exist, prepare it for creation
                records_to_create.append(
                    ShopifyOrders(
                        order_id=order_id,
                        updated_at=shopify_updated_at,
                        created_at=parse_datetime(order.created_at),
                        item_title=order.line_items[0].title if order.line_items else "N/A",
                        item_sku=order.line_items[0].sku if order.line_items else "N/A",
                        total_paid=order.total_price
                    )
                )

        # Perform bulk updates and creates
        with transaction.atomic():
            if records_to_update:
                ShopifyOrders.objects.bulk_update(
                    records_to_update,
                    fields=['updated_at', 'item_title', 'item_sku', 'total_paid']
                )
                logger.info(f"Updated {len(records_to_update)} existing records.")

            if records_to_create:
                ShopifyOrders.objects.bulk_create(records_to_create)
                logger.info(f"Created {len(records_to_create)} new records.")

        return JsonResponse({
            'message': f'{len(records_to_update)} records updated, {len(records_to_create)} records created.'
        }, status=200)

    else:
        return JsonResponse({'message': 'No orders found in the database to sync.'}, status=404)
    
        


def save_data_to_db(normalized_data, secret_surprise_data):
    try:
        # Save Shopify Orders
        shopify_orders_to_create = []
        existing_orders = set(
            ShopifyOrders.objects.values_list("order_id", "item_title", "item_sku") #add more fileds to check for duplicates
        )  # Fetch existing (order_id, item_title, item_sku) tuples
        for order in normalized_data:
            key = (order["order_id"], order["item_title"], order["item_sku"])
            if key not in existing_orders:
                shopify_orders_to_create.append(ShopifyOrders(**order))

        if shopify_orders_to_create:
            ShopifyOrders.objects.bulk_create(shopify_orders_to_create, ignore_conflicts=True)
            logger.info(f"{len(shopify_orders_to_create)} records successfully saved to the database.")
        else:
            logger.info("No records to save.")
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
            logger.info(f"{len(secret_surprises_to_create)} new Secret Surprise records successfully saved to the database.")
        else:
            logger.info("No new Secret Surprise records to save.")
    except Exception as e:
        logger.error(f"Error saving Secret Surprise records to the database: {e}")
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

@api_view(['POST'])  # Ensure it's a Django API view
def save_orders(request):
    """
    API endpoint to save Shopify orders to the database.
    """
    random_orders = [
        {
            'order_id': 'a1a6bfcbba544363a6467c0be7378f47',
            'order_date': pd.to_datetime(datetime(2025, 1, 16, 8, 36, 45, 801162)),
            'item_count': 3,
            'item_title': 'Laptop',
            'updated_at_shopify': pd.to_datetime(datetime(2025, 1, 23, 8, 36, 45, 798515)),
            'item_sku': '242499',
            'item_variant': 'Blue',
            'item_quantity': 3
        },
        {
            'order_id': 'a1a6bfcbba544363a6467c0be7378f47',
            'order_date': pd.to_datetime(datetime(2026, 1, 16, 8, 36, 45, 801162)),
            'item_count': 5,
            'item_title': 'macbook pro',
            'updated_at_shopify': pd.to_datetime(datetime(2027, 1, 23, 8, 36, 45, 798515)),
            'item_sku': '242499923423',
            'item_variant': 'grey',
            'item_quantity': 5
        }
    ]

    try:
        # Fetch existing order records
        existing_orders = set(
            testOrders.objects.values_list("order_id", "item_title", "item_sku")
        )  # Returns a set of (order_id, item_title, item_sku) tuples

        # Prepare new orders to be saved
        shopify_orders_to_create = [
            testOrders(**order) for order in random_orders
            if (order["order_id"], order["item_title"], order["item_sku"]) not in existing_orders
        ]

        # Bulk create new orders
        if shopify_orders_to_create:
            testOrders.objects.bulk_create(shopify_orders_to_create, ignore_conflicts=True)
            logger.info(f"{len(shopify_orders_to_create)} records successfully saved to the database.")
        else:
            logger.info("No new records to save.")

    except Exception as e:
        logger.error(f"Error saving Shopify orders to the database: {e}")
        return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'message': 'Data successfully saved to the database.'}, status=200)
    
    
@api_view(['POST'])
def testsync(request):
    random_orders = [
        {
            'order_id': 'a1a6bfcbba544363a6467c0be7378f47',
            'order_date': pd.to_datetime(datetime(2024, 1, 16, 8, 36, 45, 801162)),
            'item_count': 4,
            'item_title': 'macbook',
            'updated_at_shopify': pd.to_datetime(datetime(2026, 1, 23, 8, 36, 45, 798515)),
            'item_sku': '2424999',
            'item_variant': 'Red',
            'item_quantity': 4
        },
        
    ]
    
    # Fetch existing records
    existing_orders = {order.order_id: order for order in testOrders.objects.all()}  # Store existing records in a dict
    print(len(existing_orders))
    # existing_orders = {order.order_id: order for order in testOrders.objects.all()}  
    # print(f"Total fetched records: {len(existing_orders)}")
    
    print(testOrders.objects.count())  # Check total records


    records_to_update = []
    records_to_create = []

    for order in random_orders:
        shopify_updated_at = parse_datetime(str(order["updated_at_shopify"]))  # Correctly parse datetime
        order_id = order["order_id"]

        if shopify_updated_at is None:
            logger.warning(f"Invalid updated_at for order_id {order_id}. Skipping.")
            continue
        
        if timezone.is_naive(shopify_updated_at):
            shopify_updated_at = timezone.make_aware(shopify_updated_at, timezone.get_current_timezone())
        
        if order_id in existing_orders:
            existing_record = existing_orders[order_id]
            
            # Ensure existing record timestamp is also timezone-aware
            if timezone.is_naive(existing_record.updated_at_shopify):
                existing_record.updated_at_shopify = timezone.make_aware(existing_record.updated_at_shopify, timezone.get_current_timezone())
                
            if shopify_updated_at > existing_record.updated_at_shopify:
                logger.info(f"Updating order {order_id}.")
                existing_record.updated_at_shopify = shopify_updated_at
                existing_record.item_title = order["item_title"]
                existing_record.item_sku = order["item_sku"]
                existing_record.item_quantity = order["item_quantity"]
                records_to_update.append(existing_record)
        else:
            # records_to_create.append(testOrders(**order))
            logger.info(f"Order {order_id} not found in the database. Skipping.")
            continue

    # Perform database operations in a single transaction
    with transaction.atomic():
        if records_to_update:
            testOrders.objects.bulk_update(
                records_to_update,
                fields=['updated_at_shopify', 'item_title', 'item_sku', 'item_quantity', 'item_variant']
            )
            logger.info(f"Updated {len(records_to_update)} existing records.")  
        
        # if records_to_create:
        #     testOrders.objects.bulk_create(records_to_create)
        #     logger.info(f"Created {len(records_to_create)} new records.")
    
    return JsonResponse({'message': 'Data successfully saved to the database.'}, status=200)


