# Generated by Django 4.2.18 on 2025-02-20 11:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0016_alter_shopifycampaign_reffering_site'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='orders',
            name='customer',
        ),
        migrations.AddField(
            model_name='orders',
            name='billing_address_address1',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='orders',
            name='billing_address_city',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='orders',
            name='billing_address_country_code',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='orders',
            name='billing_address_latitude',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='orders',
            name='billing_address_longitude',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='orders',
            name='billing_address_name',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='orders',
            name='billing_address_province_code',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='orders',
            name='billing_address_zip',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='orders',
            name='customer_name',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='orders',
            name='shipping_address_address1',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='orders',
            name='shipping_address_city',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='orders',
            name='shipping_address_country_code',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='orders',
            name='shipping_address_latitude',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='orders',
            name='shipping_address_longitude',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='orders',
            name='shipping_address_name',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='orders',
            name='shipping_address_province_code',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='orders',
            name='shipping_address_zip',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
