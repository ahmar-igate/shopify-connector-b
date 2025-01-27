from django.db import models

class ShopifyOrders(models.Model):
    order_id = models.CharField(max_length=255, null=True, blank=True)
    order_date = models.DateTimeField(null=True, blank=True)
    item_count = models.IntegerField(null=True, blank=True)
    item_title = models.CharField(max_length=255, null=True, blank=True)
    item_sku = models.CharField(max_length=255, null=True, blank=True)
    item_variant = models.CharField(max_length=255, null=True, blank=True)
    item_quantity = models.IntegerField(null=True, blank=True)
    item_price = models.CharField(max_length=255, null=True, blank=True)
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
    customer_name = models.CharField(max_length=255, null=True, blank=True)
    shipping_address = models.TextField(null=True, blank=True)
    billing_address = models.TextField(null=True, blank=True)
    tracking_number = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=255, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.order_id


class SecretSurprise(models.Model):
    order_id = models.CharField(max_length=255, null=True, blank=True)
    item_title = models.CharField(max_length=255, null=True, blank=True)
    item_price = models.CharField(max_length=255, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.order_id


class ShopifyConnector(models.Model):
    store_name = models.CharField(max_length=255, null=True, blank=True)
    api_key = models.CharField(max_length=255, null=True, blank=True)
    password = models.CharField(max_length=255, null=True, blank=True)
    api_version = models.CharField(max_length=255, null=True, blank=True)
    min_date = models.DateTimeField(null=True, blank=True)
    max_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.store_name
