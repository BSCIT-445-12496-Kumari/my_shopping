import io
import csv
import json
import uuid
import qrcode
import base64
from datetime import date, timedelta

from django.shortcuts        import render, redirect, get_object_or_404
from django.contrib.auth     import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib          import messages
from django.db.models        import Q, Sum
from django.db               import transaction
from django.http             import JsonResponse, HttpResponse
from django.utils            import timezone
from django.views.decorators.http import require_POST

from .models  import Product, Cart, Order, OrderItem
from .forms   import RegisterForm, LoginForm, ProductForm


from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import time



# ── CHATBOT ───────────────────────────────────────────────────────────────────

from .chatbot import get_response as chatbot_response
from .models  import ChatHistory

@require_POST
def chatbot_api(request):
    """AJAX endpoint — receives user message, returns bot reply as JSON."""
    import time

    # Basic rate limiting: max 1 message per second per session
    last_msg_time = request.session.get('last_chat_time', 0)
    now = time.time()
    if now - last_msg_time < 1:
        return JsonResponse({'reply': '⏳ Please wait a moment before sending again.'})
    request.session['last_chat_time'] = now

    try:
        data    = json.loads(request.body)
        message = data.get('message', '').strip()[:500]  # limit input length
    except (json.JSONDecodeError, Exception):
        return JsonResponse({'reply': '❌ Invalid request.'}, status=400)

    if not message:
        return JsonResponse({'reply': 'Please type something! 😊'})

    reply = chatbot_response(message, user=request.user if request.user.is_authenticated else None)

    # Save to history
    ChatHistory.objects.create(
        user=request.user if request.user.is_authenticated else None,
        session_key=request.session.session_key or '',
        message=message,
        response=reply,
    )

    return JsonResponse({'reply': reply})


@staff_member_required
def chat_history_view(request):
    """Admin view to see recent chat logs."""
    chats = ChatHistory.objects.select_related('user').order_by('-created_at')[:100]
    return render(request, 'store/chat_history.html', {'chats': chats, 'cart_count': 0})


# ── HOME ──────────────────────────────────────────────────────────────────────

def home(request):
    query    = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()

    products = Product.objects.filter(is_available=True)

    if query:
        products = products.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(category__icontains=query)
        )

    if category:
        products = products.filter(category=category)

    cart_count = 0
    if request.user.is_authenticated:
        cart_count = Cart.objects.filter(user=request.user).count()

    context = {
        'products':          products,
        'query':             query,
        'selected_category': category,
        'categories':        Product.CATEGORY_CHOICES,
        'cart_count':        cart_count,
        'no_results':        query and not products.exists(),
    }
    return render(request, 'store/home.html', context)


# ── AUTH ──────────────────────────────────────────────────────────────────────

def register_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Welcome, {user.first_name}! Your account has been created.')
            return redirect('home')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = RegisterForm()
    return render(request, 'store/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Welcome back, {user.first_name or user.username}!')
            return redirect(request.GET.get('next', 'home'))
        else:
            messages.error(request, 'Invalid username or password.')
    else:
        form = LoginForm()
    return render(request, 'store/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('home')


# ── CART ──────────────────────────────────────────────────────────────────────

@login_required
def cart_view(request):
    cart_items = Cart.objects.filter(user=request.user).select_related('product')
    total      = sum(item.get_total_price() for item in cart_items)
    delivery_charge = 40 if total < 500 else 0
    grand_total = total + delivery_charge
    remaining_for_free_delivery = 500 - total if total < 500 else 0

    context = {
        'cart_items':                  cart_items,
        'total':                       total,
        'delivery_charge':             delivery_charge,
        'grand_total':                 grand_total,
        'remaining_for_free_delivery': remaining_for_free_delivery,
        'cart_count':                  cart_items.count(),
    }
    return render(request, 'store/cart.html', context)


@login_required
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id, is_available=True)

    with transaction.atomic():
        product = Product.objects.select_for_update().get(id=product_id)

        if product.stock <= 0:
            messages.error(request, f'Sorry, "{product.name}" is out of stock.')
            return redirect(request.META.get('HTTP_REFERER', 'home'))

        cart_item = Cart.objects.filter(user=request.user, product=product).first()

        if cart_item:
            cart_item.quantity += 1
            cart_item.save()
            product.stock -= 1
            product.save()
            messages.success(request, f'"{product.name}" quantity updated in your cart.')
        else:
            Cart.objects.create(user=request.user, product=product, quantity=1)
            product.stock -= 1
            product.save()
            messages.success(request, f'"{product.name}" added to your cart!')

    return redirect(request.META.get('HTTP_REFERER', 'home'))


@login_required
def remove_from_cart(request, cart_id):
    cart_item = get_object_or_404(Cart, id=cart_id, user=request.user)

    with transaction.atomic():
        product = Product.objects.select_for_update().get(id=cart_item.product.id)
        name = product.name
        product.stock += cart_item.quantity
        product.save()
        cart_item.delete()

    messages.success(request, f'"{name}" removed from your cart. Stock restored.')
    return redirect('cart')


@login_required
def update_cart(request, cart_id):
    cart_item = get_object_or_404(Cart, id=cart_id, user=request.user)
    qty = int(request.POST.get('quantity', 1))
    if qty > 0:
        cart_item.quantity = qty
        cart_item.save()
    else:
        cart_item.delete()
    return redirect('cart')


# ── PAYMENT ───────────────────────────────────────────────────────────────────

@login_required
def payment_view(request):
    cart_items = Cart.objects.filter(user=request.user).select_related('product')
    if not cart_items.exists():
        messages.warning(request, 'Your cart is empty. Add items before proceeding.')
        return redirect('cart')
    total           = sum(item.get_total_price() for item in cart_items)
    delivery_charge = 40 if total < 500 else 0
    grand_total     = total + delivery_charge

    # Generate QR code for UPI payment
    upi_id      = "freshmart@upi"
    upi_string  = f"upi://pay?pa={upi_id}&pn=FreshMart&am={grand_total}&cu=INR&tn=FreshMart+Order"
    qr          = qrcode.QRCode(version=1, box_size=6, border=2)
    qr.add_data(upi_string)
    qr.make(fit=True)
    img         = qr.make_image(fill_color="black", back_color="white")
    buffer      = io.BytesIO()
    img.save(buffer, format='PNG')
    qr_base64   = base64.b64encode(buffer.getvalue()).decode()

    context = {
        'cart_items':      cart_items,
        'total':           total,
        'delivery_charge': delivery_charge,
        'grand_total':     grand_total,
        'qr_code':         qr_base64,
        'upi_id':          upi_id,
    }
    return render(request, 'store/payment.html', context)


# ── ORDER ─────────────────────────────────────────────────────────────────────

@login_required
def place_order(request):
    if request.method == 'POST':
        cart_items = Cart.objects.filter(user=request.user).select_related('product')
        if not cart_items.exists():
            messages.warning(request, 'Your cart is empty!')
            return redirect('cart')

        payment_method  = request.POST.get('payment_method', 'cod')
        total           = sum(item.get_total_price() for item in cart_items)
        delivery_charge = 40 if total < 500 else 0
        grand_total     = total + delivery_charge

        # For QR/UPI payments mark as pending (simulate); for COD mark success immediately
        pay_status = 'pending' if payment_method in ('qr', 'upi', 'card') else 'success'

        order = Order.objects.create(
            user=request.user,
            total_amount=grand_total,
            payment_method=payment_method,
            payment_status=pay_status,
            status='pending'
        )
        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                product=item.product,
                quantity=item.quantity,
                price=item.product.price
            )
        cart_items.delete()

        if pay_status == 'pending':
            messages.info(request, f'Order #{order.id} placed. Complete payment to confirm.')
            return redirect('payment_confirm', order_id=order.id)

        messages.success(request, f'🎉 Order #{order.id} placed successfully! Your groceries are on their way.')
        return redirect('order_history')
    return redirect('payment')


# ── PAYMENT CONFIRM (QR / Simulate) ──────────────────────────────────────────

@login_required
def payment_confirm(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    # Generate QR for this specific order
    upi_id     = "freshmart@upi"
    upi_string = f"upi://pay?pa={upi_id}&pn=FreshMart&am={order.total_amount}&cu=INR&tn=Order+{order.id}"
    qr         = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(upi_string)
    qr.make(fit=True)
    img        = qr.make_image(fill_color="black", back_color="white")
    buffer     = io.BytesIO()
    img.save(buffer, format='PNG')
    qr_base64  = base64.b64encode(buffer.getvalue()).decode()

    context = {
        'order':    order,
        'qr_code':  qr_base64,
        'upi_id':   upi_id,
    }
    return render(request, 'store/payment_confirm.html', context)


@login_required
@require_POST
def simulate_payment(request, order_id):
    """Dummy endpoint — simulates payment success/failure."""
    order  = get_object_or_404(Order, id=order_id, user=request.user)
    action = request.POST.get('action', 'success')

    if action == 'success':
        order.payment_status = 'success'
        order.status         = 'processing'
        order.transaction_id = str(uuid.uuid4()).replace('-', '')[:16].upper()
        order.save()
        messages.success(request, f'✅ Payment successful! Transaction ID: {order.transaction_id}')
    else:
        order.payment_status = 'failed'
        order.save()
        messages.error(request, f'❌ Payment failed for Order #{order.id}. Please retry.')

    return redirect('order_history')


# ── ORDER HISTORY ─────────────────────────────────────────────────────────────

@login_required
def order_history(request):
    order_filter = request.GET.get('filter', 'active')

    if order_filter == 'cancelled':
        orders = Order.objects.filter(
            user=request.user, status='cancelled'
        ).prefetch_related('items__product')
    else:
        orders = Order.objects.filter(
            user=request.user,
            status__in=['pending', 'processing', 'shipped', 'delivered']
        ).prefetch_related('items__product')

    cart_count = Cart.objects.filter(user=request.user).count()

    context = {
        'orders':       orders,
        'cart_count':   cart_count,
        'order_filter': order_filter,
    }
    return render(request, 'store/order_history.html', context)


# ── ORDER CANCELLATION ────────────────────────────────────────────────────────

@login_required
def cancel_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    if request.method == 'POST':
        if order.status in ('pending', 'processing'):
            for item in order.items.select_related('product').all():
                product = item.product
                product.stock += item.quantity
                product.save()
            order.status = 'cancelled'
            order.save()
            messages.success(request, f'Order #{order.id} has been cancelled and stock has been restored.')
        else:
            messages.error(request, f'Order #{order.id} cannot be cancelled — current status is "{order.get_status_display()}".')

    return redirect('order_history')


# ── ADMIN: ORDER STATUS ───────────────────────────────────────────────────────

@staff_member_required
def admin_orders(request):
    orders = Order.objects.all().select_related('user').prefetch_related('items__product').order_by('-created_at')
    context = {
        'orders':         orders,
        'status_choices': Order.STATUS_CHOICES,
        'cart_count':     0,
    }
    return render(request, 'store/admin_orders.html', context)


@staff_member_required
def update_order_status(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if request.method == 'POST':
        new_status     = request.POST.get('status')
        valid_statuses = [s[0] for s in Order.STATUS_CHOICES]
        if new_status in valid_statuses:
            old_label    = order.get_status_display()
            order.status = new_status
            order.save()
            messages.success(request, f'Order #{order.id}: {old_label} → {order.get_status_display()}')
        else:
            messages.error(request, 'Invalid status value.')
    return redirect('admin_orders')


# ── ADMIN: PRODUCT MANAGEMENT ─────────────────────────────────────────────────

@staff_member_required
def edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, f'Product "{product.name}" updated successfully.')
            return redirect('home')
        else:
            messages.error(request, 'Please fix the errors below.')
    else:
        form = ProductForm(instance=product)
    return render(request, 'store/edit_product.html', {'form': form, 'product': product})


@staff_member_required
def delete_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if request.method == 'POST':
        name = product.name
        product.delete()
        messages.success(request, f'Product "{name}" deleted successfully.')
        return redirect('home')
    return render(request, 'store/delete_product.html', {'product': product})


# ── ABOUT ─────────────────────────────────────────────────────────────────────

def about_view(request):
    cart_count = Cart.objects.filter(user=request.user).count() if request.user.is_authenticated else 0
    return render(request, 'store/about.html', {'cart_count': cart_count})


# ── ADMIN DASHBOARD ───────────────────────────────────────────────────────────

@staff_member_required
def admin_dashboard(request):
    from django.contrib.auth.models import User

    today      = date.today()
    last7      = today - timedelta(days=6)

    total_products = Product.objects.count()
    total_orders   = Order.objects.count()
    total_users    = User.objects.filter(is_staff=False).count()
    total_revenue  = Order.objects.exclude(status='cancelled').aggregate(
                         total=Sum('total_amount'))['total'] or 0

    status_counts = {
        'pending':    Order.objects.filter(status='pending').count(),
        'processing': Order.objects.filter(status='processing').count(),
        'shipped':    Order.objects.filter(status='shipped').count(),
        'delivered':  Order.objects.filter(status='delivered').count(),
        'cancelled':  Order.objects.filter(status='cancelled').count(),
    }

    low_stock_products = Product.objects.filter(stock__lte=5, is_available=True).order_by('stock')[:8]
    recent_orders      = Order.objects.select_related('user').order_by('-created_at')[:5]

    # ── Daily Sales Chart (last 7 days) ───────────────────────────────────────
    daily_labels  = []
    daily_revenue = []
    daily_orders  = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        daily_labels.append(d.strftime('%d %b'))
        day_orders = Order.objects.filter(
            created_at__date=d
        ).exclude(status='cancelled')
        daily_revenue.append(float(day_orders.aggregate(t=Sum('total_amount'))['t'] or 0))
        daily_orders.append(day_orders.count())

    # ── Product-wise sales chart (top 8) ──────────────────────────────────────
    from django.db.models import Sum as S
    product_sales = (
        OrderItem.objects
        .values('product__name')
        .annotate(total_qty=S('quantity'))
        .order_by('-total_qty')[:8]
    )
    prod_labels = [p['product__name'] for p in product_sales]
    prod_qty    = [p['total_qty'] for p in product_sales]

    # ── Today's report ────────────────────────────────────────────────────────
    today_orders = Order.objects.filter(
        created_at__date=today
    ).exclude(status='cancelled')

    today_revenue = today_orders.aggregate(t=Sum('total_amount'))['t'] or 0
    today_items   = (
        OrderItem.objects
        .filter(order__in=today_orders)
        .values('product__name', 'product__stock')
        .annotate(sold=Sum('quantity'))
        .order_by('-sold')
    )

    context = {
        'total_products':     total_products,
        'total_orders':       total_orders,
        'total_users':        total_users,
        'total_revenue':      total_revenue,
        'status_counts':      status_counts,
        'low_stock_products': low_stock_products,
        'recent_orders':      recent_orders,
        'cart_count':         0,
        # charts
        'daily_labels':       json.dumps(daily_labels),
        'daily_revenue':      json.dumps(daily_revenue),
        'daily_orders':       json.dumps(daily_orders),
        'prod_labels':        json.dumps(prod_labels),
        'prod_qty':           json.dumps(prod_qty),
        # today report
        'today_revenue':      today_revenue,
        'today_order_count':  today_orders.count(),
        'today_items':        today_items,
        'today':              today,
    }
    return render(request, 'store/admin_dashboard.html', context)


# ── REPORT: CSV ───────────────────────────────────────────────────────────────

@staff_member_required
def report_csv(request):
    today  = date.today()
    report_date = request.GET.get('date', str(today))

    orders = Order.objects.filter(
        created_at__date=report_date
    ).exclude(status='cancelled')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="sales_report_{report_date}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Sales Report —', report_date])
    writer.writerow([])
    writer.writerow(['Order ID', 'Customer', 'Payment Method', 'Payment Status', 'Amount (₹)', 'Status', 'Time'])
    for o in orders:
        writer.writerow([
            o.id,
            o.user.username,
            o.get_payment_method_display(),
            o.get_payment_status_display(),
            o.total_amount,
            o.get_status_display(),
            o.created_at.strftime('%H:%M'),
        ])

    writer.writerow([])
    writer.writerow(['Product-wise Summary'])
    writer.writerow(['Product', 'Qty Sold', 'Remaining Stock'])

    items = (
        OrderItem.objects
        .filter(order__in=orders)
        .values('product__name', 'product__stock')
        .annotate(sold=Sum('quantity'))
        .order_by('-sold')
    )
    for item in items:
        writer.writerow([item['product__name'], item['sold'], item['product__stock']])

    total_rev = orders.aggregate(t=Sum('total_amount'))['t'] or 0
    writer.writerow([])
    writer.writerow(['Total Revenue', '', f'₹{total_rev}'])
    return response


# ── REPORT: PRINT VIEW ────────────────────────────────────────────────────────

@staff_member_required
def report_print(request):
    today       = date.today()
    report_date = request.GET.get('date', str(today))

    orders = Order.objects.filter(
        created_at__date=report_date
    ).exclude(status='cancelled').select_related('user')

    items = (
        OrderItem.objects
        .filter(order__in=orders)
        .values('product__name', 'product__stock')
        .annotate(sold=Sum('quantity'))
        .order_by('-sold')
    )
    total_rev = orders.aggregate(t=Sum('total_amount'))['t'] or 0

    context = {
        'orders':       orders,
        'items':        items,
        'total_rev':    total_rev,
        'report_date':  report_date,
        'today':        today,
    }
    return render(request, 'store/report_print.html', context)