# Generated by Django 4.2.18 on 2025-02-20 14:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0019_delete_customer'),
    ]

    operations = [
        migrations.AlterField(
            model_name='shopifyinventorydata',
            name='product_title',
            field=models.TextField(blank=True, max_length=255, null=True),
        ),
    ]
