import logging
import pandas as pd
from django.http import JsonResponse
from shopify import ShopifyResource, Order
from urllib.parse import urlparse, parse_qs
from datetime import timedelta
from django.utils.dateparse import parse_datetime
from django.db import transaction
from django.db.models import Min, Max
from django.utils.timezone import now
from .models import Orders
from rest_framework.views import APIView
from .utils import convert_to_shopify_date_format, fetch_all_records, process_shopify_records, save_data_to_db, get_store_name

logger = logging.getLogger(__name__)

def default(request):
    if request.method == 'GET':
        try:
            # Aggregate min, max order_date, and latest updated_at per store_name
            store_orders = Orders.objects.values('store_name').annotate(
                created_at_min_shopify=Min('order_date'),
                created_at_max_shopify=Max('order_date'),
                updated_at=Max('updated_at')  # Get latest updated_at per store
            )

            # Convert QuerySet to list for JSON response
            data = list(store_orders)

            # Ensure there is data before processing min/max sync dates
            if data:
                created_at_max_list = [entry['created_at_max_shopify'] for entry in data if entry['created_at_max_shopify']]
                created_at_min_list = [entry['created_at_min_shopify'] for entry in data if entry['created_at_min_shopify']]

                if created_at_max_list:
                    created_at_max = max(created_at_max_list)  # Latest max order date
                    min_date = created_at_max - timedelta(days=100)

                    if created_at_min_list:
                        created_at_min = min(created_at_min_list)
                        if min_date < created_at_min:
                            min_date = created_at_min
                    else:
                        min_date = created_at_max  # If no min date exists, set min_date to max_date

                else:
                    min_date = None
                    created_at_max = None

            else:
                min_date = None
                created_at_max = None
            print("store_order_dates: ", data)

            return JsonResponse({'store_order_dates': data, 'last_sync_min': min_date, 'last_sync_max': created_at_max})

        except Exception as e:
            logging.error(str(e))
            return JsonResponse({'error': str(e)}, status=500)

class fetch_data_shopify(APIView):
    def post(self, request, *args, **kwargs):
        print("fetch_data_shopify")
        
        try:
            data = request.data
            store_url = data.get('store_url')
            api_key = data.get('api_key')
            password = data.get('password')
            api_version = data.get('api_version')
            min_date = data.get('created_at_min')
            max_date = data.get('created_at_max')
            
            store_name = get_store_name(store_url)
            
            if not store_name:
                return JsonResponse({'error': 'Store URL not found in predefined stores'}, status=400)
            else:
                print("Store Name:", store_name)

            print(store_url, api_key, password, api_version, min_date, max_date, store_name)

            if not store_url or not api_key or not password or not api_version or not min_date or not max_date:
                return JsonResponse({'status': 'error', 'message': 'Missing required fields'})
            
            try:
                created_at_min = convert_to_shopify_date_format(min_date)
                created_at_max = convert_to_shopify_date_format(max_date)
            except ValueError as e:
                return JsonResponse({'error': str(e)}, status=400)
    
            if created_at_min > created_at_max:
                return JsonResponse({'error': 'Start date cannot be after the end date.'}, status=400)
            
            orders = fetch_all_records(api_key, password, store_url, api_version, created_at_min, created_at_max)
            if not orders:
                return JsonResponse({'status': 'error', 'message': 'No orders found'})
            order_data = process_shopify_records(orders, store_name)
            if not order_data:
                return JsonResponse({'status': 'error', 'message': 'No orders found after processing'})
            
            save_data_to_db(order_data)

            return JsonResponse({'status': 'success', 'message': 'Orders saved successfully'})
        except Exception as e:
            logging.error(str(e))
            return JsonResponse({'status': 'error', 'message': str(e)})
        
class sync_data(APIView):
    def post(self, request, *args, **kwargs):
        try:
            """
                Sync Shopify data with the database by updating matching records and adding new ones.
            """
            data = request.data
            api_key = data.get('api_key')
            password = data.get('password')
            store_url = data.get('store_url')
            api_version = data.get('api_version')
            
            store_name = get_store_name(store_url)
            
            if not store_name:
                return JsonResponse({'error': 'Store URL not found in predefined stores'}, status=400)
            else:
                print("Store Name:", store_name)

            

            if not all([api_key, password, store_url, api_version]):
                return JsonResponse({'error': 'Missing required fields'}, status=400)
    
            # Set the Shopify API URL
            shop_url = f"https://{api_key}:{password}@{store_url}/admin/api/{api_version}"
            ShopifyResource.set_site(shop_url)
            
            # Get the most recent `order_date` in the database
            created_at_range = Orders.objects.aggregate(
            created_at_min_shopify=Min('order_date'),
            created_at_max_shopify=Max('order_date')
            )

            created_at_max = created_at_range['created_at_max_shopify']
            created_at_min = created_at_range['created_at_min_shopify']
            print("created_at_min_shopify: ", created_at_min)
            print("created_at_max_shopify: ", created_at_max)
            if created_at_max:
                min_date = created_at_max - timedelta(days=100)
                if min_date < created_at_min:
                    print("min date is smalled then created_at_min")
                    min_date = created_at_min
                    
                max_date = created_at_max
                
                print("min_date: ", min_date)
                print("max_date: ", max_date)

            # Fetch existing records for comparison
            existing_orders = Orders.objects.filter(
                order_date__gte=min_date,
                order_date__lte=max_date,
                store_name=store_name
            ).values('orderID', 'updated_at_shopify', 'id', 'store_name')  

            # Convert existing orders to a dictionary for quick lookup
            existing_orders_dict = {
                order['orderID']: {'updated_at_shopify': order['updated_at_shopify'], 'id': order['id'], 'store_name': order['store_name']}
                for order in existing_orders
            }
            print("existing orders: ", existing_orders_dict)
            
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
            
            records_to_update = []
            
            for order in orders:
                shopify_updated_at = parse_datetime(order.updated_at)
                shopify_created_at = parse_datetime(order.created_at)
                # print("Shopify created at: ", shopify_created_at)
                order_id = order.name
                print("shopify_updated_at: ", shopify_updated_at)
                # print("shopify_created_at: ", shopify_created_at)
                
                print("order_id: ", order_id)
                
                if shopify_updated_at is None:
                    logger.warning(f"Invalid updated_at for order_id {order_id}. Skipping.")
                    continue
                
                if order_id in existing_orders_dict:
                    existing_order = existing_orders_dict[order_id]
                    db_updated_at_shopify = existing_order['updated_at_shopify']
                    db_id = existing_order['id']
                    print("Order: ", order)
                    # print("order: ", order.to_dict())
                    print(type(shopify_updated_at))
                    print(type(db_updated_at_shopify))
                    if db_updated_at_shopify is None or shopify_updated_at > db_updated_at_shopify:
                        logger.info(f"Updating orderID {order_id} with PK {db_id}.")

                        refunded_amount = sum(
                            float(refund.transactions[0].amount) if refund.transactions and refund.transactions[0].amount else 0.00
                            for refund in order.refunds
                        ) if order.refunds else 0.00

                        record = {
                            'id': db_id,
                            'refunded_amount': f"{refunded_amount:.2f} {order.currency if hasattr(order, 'currency') else 'USD'}",
                            'total_paid': f"{float(order.total_price or 0.00):.2f} {order.currency if hasattr(order, 'currency') else 'USD'}",
                            'payment_status': order.financial_status if hasattr(order, 'financial_status') else "unknown",
                            'fulfillment_status': order.fulfillment_status if hasattr(order, 'fulfillment_status') else "unknown",
                            'tags': order.tags if hasattr(order, 'tags') else "",
                            'status': order.status if hasattr(order, 'status') else "unknown",
                            'updated_at_shopify': shopify_updated_at,
                        }

                        print("Record being updated: ", record)  # Debugging print
                        records_to_update.append(record)
                    else:
                        # records_to_create.append(testOrders(**order))
                        logger.info(f"Skipping Order {order_id}.")
                        continue
                    
            if records_to_update:
                order_ids = [record['id'] for record in records_to_update]
                orders_to_update = Orders.objects.filter(id__in=order_ids)
            
                # Convert queryset to a dictionary for quick lookup
                orders_dict = {order.id: order for order in orders_to_update}
            
                # Modify the existing objects with new values
                for record in records_to_update:
                    order_obj = orders_dict.get(record['id'])
                    if order_obj:
                        order_obj.refunded_amount = record['refunded_amount']
                        order_obj.total_paid = record['total_paid']
                        order_obj.payment_status = record['payment_status']
                        order_obj.fulfillment_status = record['fulfillment_status']
                        order_obj.tags = record['tags']
                        order_obj.status = record['status']
                        order_obj.updated_at_shopify = record['updated_at_shopify']
                        
                        order_obj.updated_at = now()
            
                with transaction.atomic():
                    Orders.objects.bulk_update(orders_to_update, [
                        'refunded_amount', 'total_paid', 'payment_status', 'fulfillment_status',
                        'tags', 'status', 'updated_at_shopify', 'updated_at'
                    ])
            
                logger.info(f"Updated {len(records_to_update)} existing records.")
                return JsonResponse({'status': 'success', 'message': f"{len(records_to_update)} orders updated successfully"})
            else:
                logger.info("No records to update.")
                return JsonResponse({'status': 'success', 'message': 'No orders to update'})
                


        except Exception as e:
            logging.error(str(e))
            return JsonResponse({'status': 'error', 'message': str(e)})