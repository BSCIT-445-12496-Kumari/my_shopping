from django.contrib import admin
from .models import Product, Cart, Order, OrderItem


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display   = ['name', 'category', 'price', 'stock', 'is_available', 'created_at']
    list_filter    = ['category', 'is_available']
    search_fields  = ['name', 'description']
    list_editable  = ['price', 'stock', 'is_available']
    ordering       = ['-created_at']


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display  = ['user', 'product', 'quantity', 'added_at']
    search_fields = ['user__username', 'product__name']


class OrderItemInline(admin.TabularInline):
    model          = OrderItem
    extra          = 0
    readonly_fields = ['product', 'quantity', 'price']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display  = ['id', 'user', 'total_amount', 'payment_method', 'status', 'created_at']
    list_filter   = ['status', 'payment_method']
    list_editable = ['status']
    inlines       = [OrderItemInline]
    ordering      = ['-created_at']


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['order', 'product', 'quantity', 'price']



from .models import ChatHistory

@admin.register(ChatHistory)
class ChatHistoryAdmin(admin.ModelAdmin):
    list_display  = ('id', 'user', 'message', 'created_at')
    list_filter   = ('created_at',)
    search_fields = ('user__username', 'message')
    readonly_fields = ('user', 'session_key', 'message', 'response', 'created_at')