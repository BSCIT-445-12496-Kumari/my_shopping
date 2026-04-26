from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Product(models.Model):
    CATEGORY_CHOICES = [
        ('fruits',    'Fruits & Vegetables'),
        ('dairy',     'Dairy & Eggs'),
        ('bakery',    'Bakery'),
        ('beverages', 'Beverages'),
        ('snacks',    'Snacks'),
        ('grains',    'Grains & Cereals'),
        ('meat',      'Meat & Seafood'),
        ('frozen',    'Frozen Foods'),
        ('personal',  'Personal Care'),
        ('household', 'Household'),
        ('other',     'Other'),
    ]

    name         = models.CharField(max_length=200)
    description  = models.TextField(blank=True)
    price        = models.DecimalField(max_digits=10, decimal_places=2)
    stock        = models.PositiveIntegerField(default=0)
    category     = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='other')
    image_url    = models.URLField(max_length=1000, blank=True, null=True)
    is_available = models.BooleanField(default=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-created_at']


class Cart(models.Model):
    user     = models.ForeignKey(User, on_delete=models.CASCADE)
    product  = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')

    def __str__(self):
        return f"{self.user.username} - {self.product.name} x {self.quantity}"

    def get_total_price(self):
        return self.product.price * self.quantity


class Order(models.Model):
    STATUS_CHOICES = [
        ('pending',    'Pending'),
        ('processing', 'Processing'),
        ('shipped',    'Shipped'),
        ('delivered',  'Delivered'),
        ('cancelled',  'Cancelled'),
    ]

    PAYMENT_CHOICES = [
        ('upi',  'UPI'),
        ('card', 'Credit/Debit Card'),
        ('cod',  'Cash on Delivery'),
        ('qr',   'QR Code Payment'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed',  'Failed'),
    ]

    user              = models.ForeignKey(User, on_delete=models.CASCADE)
    total_amount      = models.DecimalField(max_digits=10, decimal_places=2)
    status            = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_method    = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default='cod')
    payment_status    = models.CharField(max_length=10, choices=PAYMENT_STATUS_CHOICES, default='pending')
    transaction_id    = models.CharField(max_length=100, blank=True, null=True)
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order #{self.id} by {self.user.username}"

    class Meta:
        ordering = ['-created_at']


class OrderItem(models.Model):
    order    = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product  = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price    = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"

    def get_total_price(self):
        return self.price * self.quantity



class ChatHistory(models.Model):
    user       = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    session_key = models.CharField(max_length=100, blank=True, null=True)
    message    = models.TextField()
    response   = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Chat by {self.user or 'Guest'} at {self.created_at:%d %b %H:%M}"