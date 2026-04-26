"""
FreshMart Chatbot — keyword-based NLP engine.
All logic lives here; views.py just calls get_response().
"""

import re
from django.db.models import Q
from .models import Product, Order


# ── Store info (edit these to match your store) ───────────────────────────────
STORE_INFO = {
    'name':    'FreshMart',
    'phone':   '+91 6205628253',
    'email':   'Rahulkumar@gmail.com',
    'address': 'Kurji, Chasma Center, Food District, Patna - 80010',
    'hours':   'Monday – Saturday: 8:00 AM – 10:00 PM',
    'delivery':'Free delivery on orders above ₹500. ₹40 delivery charge below ₹500.',
    'returns': 'Easy returns within 24 hours of delivery. Contact support.',
}


# ── FAQ bank ──────────────────────────────────────────────────────────────────
FAQS = [
    {
        'keywords': ['timing', 'time', 'open', 'close', 'hour', 'working', 'schedule'],
        'answer': (
            f"🕐 We are open <b>Monday – Saturday, 8:00 AM – 10:00 PM</b>.<br>"
            f"Sunday: 9:00 AM – 8:00 PM.<br>"
            f"You can place orders 24/7 on our website!"
        ),
    },
    {
        'keywords': ['payment', 'pay', 'method', 'upi', 'card', 'cod', 'cash', 'online'],
        'answer': (
            "💳 We accept the following payment methods:<br>"
            "• <b>UPI</b> — Google Pay, PhonePe, Paytm, BHIM<br>"
            "• <b>Credit / Debit Card</b> — Visa, Mastercard, RuPay<br>"
            "• <b>QR Code</b> — Scan & pay instantly<br>"
            "• <b>Cash on Delivery (COD)</b> — Pay when your order arrives"
        ),
    },
    {
        'keywords': ['deliver', 'delivery', 'shipping', 'ship', 'fast', 'when', 'arrive', 'reach'],
        'answer': (
            "🚚 Delivery details:<br>"
            "• Orders within Patna: delivered within <b>2–4 hours</b><br>"
            "• Free delivery on orders ₹500 and above<br>"
            "• ₹40 delivery charge for orders below ₹500<br>"
            "• Track your order in <b>My Orders</b> section"
        ),
    },
    {
        'keywords': ['return', 'refund', 'exchange', 'replace', 'damage', 'broken', 'wrong'],
        'answer': (
            "🔄 Our return policy:<br>"
            "• Returns accepted within <b>24 hours</b> of delivery<br>"
            "• Refund processed within 3–5 business days<br>"
            "• Contact us at <b>Rahulkumar@gmail.com</b> or call <b>+91 6205628253</b>"
        ),
    },
    {
        'keywords': ['place', 'how', 'order', 'buy', 'purchase', 'shop', 'add', 'cart'],
        'answer': (
            "🛒 How to place an order:<br>"
            "1. Browse products on the <b>Home</b> page<br>"
            "2. Click <b>Add to Cart</b> on any product<br>"
            "3. Go to <b>Cart</b> and review your items<br>"
            "4. Click <b>Proceed to Payment</b><br>"
            "5. Choose a payment method and confirm<br>"
            "That's it — your groceries are on their way! 🎉"
        ),
    },
    {
        'keywords': ['cancel', 'cancellation', 'stop', 'abort'],
        'answer': (
            "❌ To cancel an order:<br>"
            "• Go to <b>My Orders</b><br>"
            "• Click <b>Cancel Order</b> (only available for Pending/Processing orders)<br>"
            "• Stock is restored automatically after cancellation<br>"
            "• Shipped or delivered orders cannot be cancelled"
        ),
    },
    {
        'keywords': ['account', 'register', 'signup', 'sign up', 'login', 'log in', 'password', 'forgot'],
        'answer': (
            "👤 Account help:<br>"
            "• <a href='/register/'>Register here</a> to create a free account<br>"
            "• <a href='/login/'>Login here</a> if you already have one<br>"
            "• Forgot password? Use the <a href='/password-reset/'>Reset Password</a> link on the login page"
        ),
    },
    {
        'keywords': ['contact', 'support', 'help', 'reach', 'phone', 'email', 'address', 'location'],
        'answer': (
            f"📞 Contact FreshMart:<br>"
            f"• 📱 Phone: <b>{STORE_INFO['phone']}</b><br>"
            f"• 📧 Email: <b>{STORE_INFO['email']}</b><br>"
            f"• 📍 Address: {STORE_INFO['address']}<br>"
            f"• 🕐 Hours: {STORE_INFO['hours']}"
        ),
    },
    {
        'keywords': ['discount', 'offer', 'coupon', 'promo', 'deal', 'sale', 'cheap', 'price'],
        'answer': (
            "🏷️ Current offers:<br>"
            "• <b>Free delivery</b> on orders above ₹500<br>"
            "• Check the home page regularly for seasonal deals<br>"
            "• Subscribe to our newsletter for exclusive offers!"
        ),
    },
    {
        'keywords': ['stock', 'available', 'availability', 'out of stock', 'in stock'],
        'answer': (
            "📦 Product availability:<br>"
            "• Products marked <b>Available</b> are in stock<br>"
            "• Out-of-stock products cannot be added to cart<br>"
            "• Type a product name to check its availability instantly!"
        ),
    },
    {
        'keywords': ['hi', 'hello', 'hey', 'hii', 'helo', 'good morning', 'good evening', 'namaste', 'namaskar'],
        'answer': (
            "👋 Hello! Welcome to <b>FreshMart Support</b>!<br>"
            "I'm your virtual assistant. I can help you with:<br>"
            "• 🛒 Product search & availability<br>"
            "• 📦 Order tracking<br>"
            "• 💳 Payment information<br>"
            "• 🕐 Store timings & contact<br><br>"
            "What can I help you with today?"
        ),
    },
    {
        'keywords': ['thank', 'thanks', 'bye', 'goodbye', 'ok', 'okay', 'great', 'nice', 'awesome'],
        'answer': (
            "😊 You're welcome! Happy shopping at <b>FreshMart</b>!<br>"
            "If you need anything else, I'm right here. 🛒"
        ),
    },
]


# ── Helper: clean & tokenise input ────────────────────────────────────────────

def _clean(text: str) -> str:
    return re.sub(r'[^\w\s]', ' ', text.lower()).strip()


def _tokens(text: str) -> list:
    return _clean(text).split()


# ── Core matcher ──────────────────────────────────────────────────────────────

def _match_faq(text: str) -> str | None:
    cleaned = _clean(text)
    tokens  = set(_tokens(text))
    best_score = 0
    best_answer = None

    for faq in FAQS:
        score = sum(1 for kw in faq['keywords'] if kw in cleaned or kw in tokens)
        if score > best_score:
            best_score  = score
            best_answer = faq['answer']

    return best_answer if best_score > 0 else None


def _search_products(text: str):
    """Return up to 3 matching products."""
    words = [w for w in _tokens(text) if len(w) > 2]
    if not words:
        return None

    q = Q()
    for w in words:
        q |= Q(name__icontains=w) | Q(description__icontains=w) | Q(category__icontains=w)

    products = Product.objects.filter(q, is_available=True)[:3]
    return products if products.exists() else None


def _build_product_reply(products) -> str:
    lines = ["🔍 Here's what I found:<br>"]
    for p in products:
        stock_label = (
            "✅ In Stock" if p.stock > 5
            else f"⚠️ Only {p.stock} left"
            if p.stock > 0 else "❌ Out of Stock"
        )
        lines.append(
            f"<div class='chat-product-card'>"
            f"<b>{p.name}</b> — ₹{p.price}<br>"
            f"<small>{p.get_category_display()} &nbsp;|&nbsp; {stock_label}</small>"
            f"</div>"
        )
    lines.append("<small>Visit the <a href='/'>Home page</a> to add items to your cart.</small>")
    return "".join(lines)


def _get_order_status(user) -> str:
    if not user or not user.is_authenticated:
        return (
            "🔐 Please <a href='/login/'>log in</a> to check your order status."
        )

    orders = Order.objects.filter(user=user).order_by('-created_at')[:3]
    if not orders.exists():
        return "📭 You haven't placed any orders yet. <a href='/'>Start shopping!</a>"

    lines = ["📦 Your recent orders:<br>"]
    for o in orders:
        pay_badge = {
            'success': '✅',
            'failed':  '❌',
            'pending': '⏳',
        }.get(o.payment_status, '⏳')

        lines.append(
            f"<div class='chat-order-card'>"
            f"<b>Order #{o.id}</b> — ₹{o.total_amount}<br>"
            f"<small>Status: <b>{o.get_status_display()}</b> &nbsp;|&nbsp; "
            f"Payment: {pay_badge} {o.get_payment_status_display()}<br>"
            f"Placed: {o.created_at:%d %b %Y}</small>"
            f"</div>"
        )

    lines.append("<a href='/orders/'>View all orders →</a>")
    return "".join(lines)


# ── Public API ─────────────────────────────────────────────────────────────────

ORDER_KEYWORDS = {'order', 'orders', 'track', 'tracking', 'status', 'where', 'shipped', 'delivered', 'my order'}
PRODUCT_STOP_WORDS = {
    'what', 'when', 'how', 'why', 'is', 'the', 'are', 'does',
    'do', 'can', 'tell', 'show', 'about', 'much', 'cost', 'price',
}


def get_response(text: str, user=None) -> str:
    """
    Main entry point.
    Returns an HTML string to display in the chat bubble.
    """
    if not text or not text.strip():
        return "Please type a message and I'll be happy to help! 😊"

    cleaned = _clean(text)
    tokens  = set(_tokens(text))

    # 1. Greeting / farewell — highest priority
    greet_words = {'hi', 'hello', 'hey', 'hii', 'namaste', 'bye', 'goodbye', 'thank', 'thanks'}
    if tokens & greet_words:
        answer = _match_faq(text)
        if answer:
            return answer

    # 2. Order tracking
    if tokens & ORDER_KEYWORDS:
        # If it also has non-order words, might be "how to order" → try FAQ first
        faq = _match_faq(text)
        if faq and ('how' in tokens or 'place' in tokens or 'buy' in tokens):
            return faq
        return _get_order_status(user)

    # 3. FAQ matching
    faq_answer = _match_faq(text)
    if faq_answer:
        return faq_answer

    # 4. Product search
    search_tokens = tokens - PRODUCT_STOP_WORDS - ORDER_KEYWORDS
    if search_tokens:
        products = _search_products(text)
        if products:
            return _build_product_reply(products)

    # 5. Fallback
    return (
        "🤔 I'm not sure about that. Here's what I can help with:<br>"
        "<ul style='margin:6px 0 0 16px;padding:0'>"
        "<li>Type a <b>product name</b> to check price & availability</li>"
        "<li>Ask about <b>my order</b> to see order status</li>"
        "<li>Ask about <b>delivery</b>, <b>payment</b>, or <b>timings</b></li>"
        "<li>Type <b>contact</b> for support details</li>"
        "</ul>"
    )