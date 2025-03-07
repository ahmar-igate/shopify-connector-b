from django.db import models

# class Customer(models.Model):
#     id = models.AutoField(primary_key=True)
#     customer_name = models.CharField(max_length=255, null=True, blank=True)
#     shipping_address = models.TextField(null=True, blank=True)
#     billing_address = models.TextField(null=True, blank=True)
#     billing_address_latitude = models.TextField(null=True, blank=True)
#     billing_address_longitude = models.TextField(null=True, blank=True)
#     shipping_address_longitude = models.TextField(null=True, blank=True)
#     shipping_address_latitude = models.TextField(null=True, blank=True)
    
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     def __str__(self):
#         return self.customer_name

class Orders(models.Model):
    id = models.AutoField(primary_key=True)
    # customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    
    orderID = models.CharField(max_length=255, unique=True)
    customer_name = models.CharField(max_length=255, null=True, blank=True)
    shipping_address_name = models.CharField(max_length=255, null=True, blank=True)
    billing_address_name = models.CharField(max_length=255, null=True, blank=True)
    shipping_address_address1 = models.TextField(null=True, blank=True)
    billing_address_address1 = models.TextField(null=True, blank=True)
    shipping_address_city = models.CharField(max_length=255, null=True, blank=True)
    billing_address_city = models.CharField(max_length=255, null=True, blank=True)
    shipping_address_zip = models.CharField(max_length=255, null=True, blank=True)
    billing_address_zip = models.CharField(max_length=255, null=True, blank=True)
    shipping_address_province_code = models.CharField(max_length=255, null=True, blank=True)
    shipping_address_country_code = models.CharField(max_length=255, null=True, blank=True)
    billing_address_country_code = models.CharField(max_length=255, null=True, blank=True)
    billing_address_province_code = models.CharField(max_length=255, null=True, blank=True)
    
    billing_address_latitude = models.TextField(null=True, blank=True)
    billing_address_longitude = models.TextField(null=True, blank=True)
    shipping_address_longitude = models.TextField(null=True, blank=True)
    shipping_address_latitude = models.TextField(null=True, blank=True)
    order_processed_at = models.DateTimeField(null=True, blank=True)
    order_created_at = models.DateTimeField(null=True, blank=True)
    item_count = models.IntegerField(null=True, blank=True)
    shipping_price = models.CharField(max_length=255, null=True, blank=True)
    delivery_method = models.CharField(max_length=255, null=True, blank=True)
    delivery_status = models.CharField(max_length=255, null=True, blank=True)
    discount_code = models.CharField(max_length=255, null=True, blank=True)
    discount_type = models.CharField(max_length=255, null=True, blank=True)
    discount_amount = models.CharField(max_length=255, null=True, blank=True)
    total_discount_amount = models.CharField(max_length=255, null=True, blank=True)
    refunded_amount = models.CharField(max_length=255, null=True, blank=True)
    total_paid = models.CharField(max_length=255, null=True, blank=True)
    payment_status = models.CharField(max_length=255, null=True, blank=True)
    fulfillment_status = models.CharField(max_length=255, null=True, blank=True)
    channel = models.CharField(max_length=255, null=True, blank=True)
    destination = models.CharField(max_length=255, null=True, blank=True)
    tags = models.CharField(max_length=255, null=True, blank=True)
    tracking_number = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=255, null=True, blank=True)
    store_name = models.CharField(max_length=255, null=True, blank=True)
    
    landing_site = models.TextField(null=True, blank=True)
    order_status_url = models.CharField(max_length=255, null=True, blank=True)
    referring_site = models.TextField(null=True, blank=True)
    payment_gateway_names = models.CharField(max_length=255, null=True, blank=True)
    # created_at_shopify = models.DateTimeField(null=True, blank=True)
    updated_at_shopify = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.orderID} - {self.fulfillment_status}"


class OrderItems(models.Model):
    id = models.AutoField(primary_key=True)
    order = models.ForeignKey(Orders, on_delete=models.CASCADE, related_name='order_items')
    item_title = models.CharField(max_length=255, null=True, blank=True)
    item_sku = models.CharField(max_length=255, null=True, blank=True)
    item_variant = models.CharField(max_length=255, null=True, blank=True)
    item_quantity = models.IntegerField(null=True, blank=True)
    item_price = models.CharField(max_length=255, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.item_title


class ShopifyInventoryData(models.Model):
    id = models.AutoField(primary_key=True)
    product_id = models.CharField(max_length=255, null=True, blank=True)
    product_title = models.TextField(max_length=255, null=True, blank=True)
    vendor = models.CharField(max_length=255, null=True, blank=True)
    tags = models.CharField(max_length=255, null=True, blank=True)
    product_type = models.CharField(max_length=255, null=True, blank=True)
    category = models.TextField(max_length=255, null=True, blank=True)
    category_name = models.CharField(max_length=255, null=True, blank=True)
    collections = models.TextField(max_length=255, null=True, blank=True)
    variant_id = models.CharField(max_length=255, null=True, blank=True)
    variant_title = models.TextField(max_length=255, null=True, blank=True)
    variant_sku = models.CharField(max_length=255, null=True, blank=True)
    location_id = models.CharField(max_length=255, null=True, blank=True)
    location_name = models.CharField(max_length=255, null=True, blank=True)
    available = models.IntegerField(default=0)
    reserved = models.IntegerField(default=0)
    incoming = models.IntegerField(default=0)
    committed = models.IntegerField(default=0)
    damaged = models.IntegerField(default=0)  
    on_hand = models.IntegerField(default=0)
    quality_control = models.IntegerField(default=0)
    safety_check = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.product_title} - {self.variant_title}"
    
    
class ShopifyCampaign(models.Model):
    id = models.AutoField(primary_key=True)
    order = models.ForeignKey(Orders, on_delete=models.CASCADE, related_name='order_campaigns')
    utm_id = models.CharField(max_length=255, null=True, blank=True)
    campaign_id = models.CharField(max_length=255, null=True, blank=True)
    shopif_order_id = models.CharField(max_length=255, null=True, blank=True)
    landing_site = models.TextField(null=True, blank=True)
    cmp_id = models.CharField(max_length=255, null=True, blank=True)
    utm_campaign = models.CharField(max_length=255, null=True, blank=True)
    utm_source = models.CharField(max_length=255, null=True, blank=True)
    utm_medium = models.CharField(max_length=255, null=True, blank=True)
    reffering_site = models.TextField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.shopif_order_id} - {self.utm_campaign}"