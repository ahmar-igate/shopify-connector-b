# Generated by Django 4.2.18 on 2025-02-11 17:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0015_alter_orders_referring_site'),
    ]

    operations = [
        migrations.AlterField(
            model_name='shopifycampaign',
            name='reffering_site',
            field=models.TextField(blank=True, null=True),
        ),
    ]
