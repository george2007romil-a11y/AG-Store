from decimal import Decimal
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from .models import Coupon, CustomerProfile
from django.db import transaction
from django.utils import timezone
from .models import Product, Order, OrderItem


def home(request):
    search_query = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()

    products = Product.objects.all().order_by('-created_at')

    if search_query:
        products = products.filter(
            name__icontains=search_query
        ) | products.filter(
            description__icontains=search_query
        )

    if category in dict(Product.CATEGORY_CHOICES):
        products = products.filter(category=category)

    cart = request.session.get('cart', {})
    cart_count = sum(cart.values())

    return render(request, 'store/home.html', {
        'products': products,
        'categories': Product.CATEGORY_CHOICES,
        'cart_count': cart_count,
    })



def add_to_cart(request, product_id):
    if request.method != 'POST':
        return redirect('home')

    product = get_object_or_404(Product, id=product_id)

    cart = request.session.get('cart', {})
    product_id = str(product_id)

    current_quantity = int(cart.get(product_id, 0))

    if current_quantity < product.stock:
        cart[product_id] = current_quantity + 1

    request.session['cart'] = cart
    request.session.modified = True

    return redirect('cart')

def cart(request):
    cart_data = request.session.get('cart', {})
    cart_items = []
    total = 0
    cleaned_cart = {}

    for product_id, quantity in cart_data.items():
        product = Product.objects.filter(id=product_id).first()

        if product is None:
            continue

        quantity = int(quantity)

        if quantity <= 0:
            continue

        subtotal = product.price * quantity
        total += subtotal

        cleaned_cart[str(product_id)] = quantity

        cart_items.append({
            'product': product,
            'quantity': quantity,
            'subtotal': subtotal,
        })

    request.session['cart'] = cleaned_cart
    request.session.modified = True

    return render(request, 'store/cart.html', {
        'cart_items': cart_items,
        'total': total,
    }) 
def update_cart(request, product_id, action):
    if request.method != 'POST':
        return redirect('cart')

    cart = request.session.get('cart', {})
    product_id = str(product_id)

    if product_id in cart:
        if action == 'increase':
            product = get_object_or_404(Product, id=product_id)

            if cart[product_id] < product.stock:
                cart[product_id] += 1

        elif action == 'decrease':
            cart[product_id] -= 1

            if cart[product_id] <= 0:
                del cart[product_id]

    request.session['cart'] = cart
    request.session.modified = True

    return redirect('cart')



def remove_from_cart(request, product_id):
    if request.method != 'POST':
        return redirect('cart')

    cart = request.session.get('cart', {})
    product_id = str(product_id)

    if product_id in cart:
        del cart[product_id]

    request.session['cart'] = cart
    request.session.modified = True

    return redirect('cart')



def checkout(request):
    profile = None
    if request.user.is_authenticated:
        profile = CustomerProfile.objects.filter(user=request.user).first()

    cart_data = request.session.get('cart', {})
    cart_items = []
    total = Decimal('0.00')

    for product_id, quantity in cart_data.items():
        product = get_object_or_404(Product, id=product_id)
        quantity = min(int(quantity), product.stock)

        if quantity > 0:
            subtotal = product.price * quantity
            total += subtotal
            cart_items.append({
                'product': product,
                'quantity': quantity,
                'subtotal': subtotal,
            })

    if not cart_items:
        return redirect('cart')

    coupon_code = request.POST.get(
        'coupon_code',
        request.session.get('coupon_code', '')
    ).strip().upper() if request.method == 'POST' else request.session.get('coupon_code', '')

    coupon = None
    discount = Decimal('0.00')
    coupon_error = None

    if coupon_code:
        now = timezone.now()
        coupon = Coupon.objects.filter(
            code__iexact=coupon_code,
            active=True
        ).first()

        if not coupon:
            coupon_error = 'Invalid or inactive coupon.'
        elif coupon.valid_from and now < coupon.valid_from:
            coupon_error = 'This coupon is not active yet.'
        elif coupon.valid_until and now > coupon.valid_until:
            coupon_error = 'This coupon has expired.'
        elif total < coupon.minimum_order:
            coupon_error = 'Your order does not meet the minimum amount.'
        elif not 1 <= coupon.discount_percent <= 100:
            coupon_error = 'This coupon has an invalid discount percentage.'
        else:
            discount = (total * Decimal(coupon.discount_percent) / Decimal('100')).quantize(Decimal('0.01'))
            if coupon.maximum_discount is not None:
                discount = min(discount, coupon.maximum_discount)
            discount = min(discount, total)

    if request.method == 'POST':
        customer_name = request.POST.get('customer_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        address = request.POST.get('address', '').strip()

        if not customer_name or not phone or not address:
            return render(request, 'store/checkout.html', {
                'cart_items': cart_items,
                'total': total,
                'profile': profile,
                'coupon_code': coupon_code,
                'discount': discount,
                'final_total': total - discount + Decimal(settings.SHIPPING_FEE),
                'shipping_fee': Decimal(settings.SHIPPING_FEE),
                'coupon_error': 'Name, phone, and address are required.',
            })

        if coupon_code and coupon_error:
            return render(request, 'store/checkout.html', {
                'cart_items': cart_items,
                'total': total,
                'profile': profile,
                'coupon_code': coupon_code,
                'discount': Decimal('0.00'),
                'final_total': total + Decimal(settings.SHIPPING_FEE),
                'shipping_fee': Decimal(settings.SHIPPING_FEE),
                'coupon_error': coupon_error,
            })

        with transaction.atomic():
            for item in cart_items:
                product = Product.objects.select_for_update().get(
                    id=item['product'].id
                )
                if item['quantity'] > product.stock:
                    return redirect('cart')
                item['product'] = product
                item['subtotal'] = product.price * item['quantity']

            total = sum((item['subtotal'] for item in cart_items), Decimal('0.00'))

            if coupon_code:
                now = timezone.now()
                coupon = Coupon.objects.filter(code__iexact=coupon_code, active=True).first()
                if (
                    not coupon
                    or (coupon.valid_from and now < coupon.valid_from)
                    or (coupon.valid_until and now > coupon.valid_until)
                    or total < coupon.minimum_order
                    or not 1 <= coupon.discount_percent <= 100
                ):
                    return render(request, 'store/checkout.html', {
                        'cart_items': cart_items,
                        'total': total,
                        'profile': profile,
                        'coupon_code': coupon_code,
                        'discount': Decimal('0.00'),
                        'final_total': total + Decimal(settings.SHIPPING_FEE),
                'shipping_fee': Decimal(settings.SHIPPING_FEE),
                        'coupon_error': 'Coupon is no longer valid. Please review your order.',
                    })

                discount = (total * Decimal(coupon.discount_percent) / Decimal('100')).quantize(Decimal('0.01'))
                if coupon.maximum_discount is not None:
                    discount = min(discount, coupon.maximum_discount)
                discount = min(discount, total)

            order = Order.objects.create(
                user=request.user if request.user.is_authenticated else None,
                customer_name=customer_name,
                phone=phone,
                address=address,
                total_price=total - discount + Decimal(settings.SHIPPING_FEE),
                shipping_fee=Decimal(settings.SHIPPING_FEE),
                discount_amount=discount,
                coupon_code=coupon.code if coupon_code and coupon else '',
            )

            for item in cart_items:
                product = item['product']
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=item['quantity'],
                    price=product.price,
                )
                product.stock -= item['quantity']
                product.save(update_fields=['stock'])

        request.session['cart'] = {}
        request.session.pop('coupon_code', None)
        request.session.modified = True
        return redirect('order_success', order_id=order.id)

    return render(request, 'store/checkout.html', {
        'cart_items': cart_items,
        'total': total,
        'profile': profile,
        'coupon_code': coupon_code,
        'discount': discount,
        'final_total': total - discount + Decimal(settings.SHIPPING_FEE),
                'shipping_fee': Decimal(settings.SHIPPING_FEE),
        'coupon_error': coupon_error,
    })



def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    items_total = sum(
        (item.price * item.quantity for item in order.items.all()),
        Decimal('0.00')
    )

    return render(request, 'store/order_success.html', {
        'order': order,
        'items_total': items_total,
    })


def signup(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        phone = request.POST.get('phone', '').strip()
        address = request.POST.get('address', '').strip()
        referral_code = request.POST.get('referral_code', '').strip().upper()

        if not username or not password:
            return render(request, 'store/signup.html', {
                'error': 'Username and password are required.'
            })

        if User.objects.filter(username=username).exists():
            return render(request, 'store/signup.html', {
                'error': 'Username already exists.'
            })

        referrer = None
        if referral_code:
            referrer = CustomerProfile.objects.filter(
                referral_code=referral_code
            ).first()
            if not referrer:
                return render(request, 'store/signup.html', {
                    'error': 'Invalid referral code.',
                    'referral_code': referral_code,
                })

        user = User.objects.create_user(username=username, password=password)
        CustomerProfile.objects.create(
            user=user,
            phone=phone,
            address=address,
            referred_by=referrer,
        )
        login(request, user)
        return redirect('home')

    return render(request, 'store/signup.html')

def user_login(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('home')

        return render(request, 'store/login.html', {'error': 'Invalid username or password.'})

    return render(request, 'store/login.html')


def user_logout(request):
    logout(request)
    return redirect('home')

def my_orders(request):
    if not request.user.is_authenticated:
        return redirect('login')

    orders = Order.objects.filter(
        user=request.user
    ).prefetch_related('items__product').order_by('-created_at')

    return render(request, 'store/my_orders.html', {
        'orders': orders,
    })


def track_order(request):
    order = None
    error = None

    if request.method == 'POST':
        order_id = request.POST.get('order_id', '').strip()
        phone = request.POST.get('phone', '').strip()

        if order_id and phone:
            try:
                order = Order.objects.get(id=order_id, phone=phone)
            except (Order.DoesNotExist, ValueError):
                error = 'Order not found.'
        else:
            error = 'Enter both order number and phone number.'

    return render(request, 'store/track_order.html', {
        'order': order,
        'error': error,
    })
