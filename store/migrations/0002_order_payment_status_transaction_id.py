from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='payment_status',
            field=models.CharField(
                choices=[('pending', 'Pending'), ('success', 'Success'), ('failed', 'Failed')],
                default='pending',
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='transaction_id',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name='order',
            name='payment_method',
            field=models.CharField(
                choices=[('upi', 'UPI'), ('card', 'Credit/Debit Card'), ('cod', 'Cash on Delivery'), ('qr', 'QR Code Payment')],
                default='cod',
                max_length=10,
            ),
        ),
    ]