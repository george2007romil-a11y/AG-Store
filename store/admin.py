from django.contrib import admin
from .models import Product, ProductImage, Order, OrderItem, Coupon


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 2


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'category',
        'price',
        'cost_price',
        'old_price',
        'stock',
        'created_at',
    )
    list_filter = ('category',)
    search_fields = ('name', 'description')
    inlines = [ProductImageInline]
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'quantity', 'price')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'customer_name',
        'phone',
        'total_price',
        'status',
        'created_at',
    )

    search_fields = (
        'customer_name',
        'phone',
        'address',
    )

    list_filter = ('status', 'created_at')

    inlines = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = (
        'order',
        'product',
        'quantity',
        'price',
    )


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ("code", "discount_percent", "active", "valid_from", "valid_until", "minimum_order")
    search_fields = ("code",)
    list_filter = ("active",)
