# Generated by Django 4.2.18 on 2025-02-03 11:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0006_orders_store_name'),
    ]

    operations = [
        migrations.RenameField(
            model_name='orders',
            old_name='order_date',
            new_name='order_created_at',
        ),
        migrations.AddField(
            model_name='orders',
            name='order_processed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
