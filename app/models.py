from django.db import models

class Customer(models.Model):
    id = models.AutoField(primary_key=True)
    # order = models.ForeignKey(Orders, on_delete=models.CASCADE, related_name='customers', db_column='OrderID')
    customer_name = models.CharField(max_length=255, null=True, blank=True)
    shipping_address = models.TextField(null=True, blank=True)
    billing_address = models.TextField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.customer_name

class Orders(models.Model):
    id = models.AutoField(primary_key=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    orderID = models.CharField(max_length=255, unique=True)
    order_date = models.DateTimeField(null=True, blank=True)
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





# class SecretSurpriseOrders(models.Model):
#     id = models.AutoField(primary_key=True)
#     item = models.ForeignKey(OrderItems, on_delete=models.CASCADE, related_name='secret_surprises')
#     item_title = models.CharField(max_length=255, null=True, blank=True)
#     item_price = models.CharField(max_length=255, null=True, blank=True)

#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     def __str__(self):
#         return self.item_title
