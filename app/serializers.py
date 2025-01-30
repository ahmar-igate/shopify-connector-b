from rest_framework import serializers
from .models_backup import ShopifyOrders, SecretSurprise, ShopifyConnector

class ShopifyOrdersSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShopifyOrders
        fields = [
            'id', 'order_id', 'order_date', 'item_count', 'item_title', 'item_sku',
            'item_variant', 'item_quantity', 'item_price', 'shipping_price', 'delivery_method',
            'delivery_status', 'discount_code', 'discount_type', 'discount_amount',
            'total_discount_amount', 'refunded_amount', 'total_paid', 'payment_status',
            'fulfillment_status', 'channel', 'destination', 'tags', 'customer_name',
            'shipping_address', 'billing_address', 'tracking_number', 'status',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']  # Fields auto-managed by Django


class SecretSurpriseSerializer(serializers.ModelSerializer):
    class Meta:
        model = SecretSurprise
        fields = ['id', 'order_id', 'item_title', 'item_price', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']



class ShopifyConnectorSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShopifyConnector
        fields = [
            'id', 'store_name', 'api_key', 'password', 'api_version', 'min_date',
            'max_date', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


    def to_representation(self, instance):
        """
        Customize the serialized output by hiding sensitive fields like `api_key` and `password`.
        """
        representation = super().to_representation(instance)
        representation.pop('api_key', None)
        representation.pop('password', None)
        return representation
