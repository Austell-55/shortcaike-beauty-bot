# templates.py
# All reply messages for the Shortcaike Beauty Stores WhatsApp bot

def get_greeting(name: str = None) -> str:
    if name:
        return f"Welcome back, {name}! How can I help you today?"
    return "Hello! Welcome to Shortcaike Beauty Stores. How can I help you today?"

def get_name_acknowledgment(name: str) -> str:
    return f"Nice to meet you, {name}. Welcome to Shortcaike Beauty Stores, where beauty is our priority. Feel free to ask me anything about our products or skincare."

def get_recommendation(product_name: str, price: int, description: str, condition: str) -> str:
    return f"For {condition} skin, I recommend our {product_name} at ₦{price}. {description} Should I add it to your cart?"

def get_add_to_cart_confirmation(product_name: str) -> str:
    return f"{product_name} has been added to your cart."

def get_remove_confirmation(product_name: str) -> str:
    return f"{product_name} has been removed from your cart."

def get_show_cart(cart: list, total: float) -> str:
    if not cart:
        return "Your cart is empty."
    items_text = "\n".join([f"- {item['name']} x{item['quantity']}: ₦{item['price']*item['quantity']}" for item in cart])
    return f"Your cart has:\n{items_text}\nTotal: ₦{total}\n\nWould you like to check out or continue shopping?"

def get_clear_cart_confirmation() -> str:
    return "Your cart has been cleared."

def get_delivery_options() -> str:
    return "Please select your delivery option:\n1. Home Delivery (fee applies)\n2. Express Delivery (same day, higher fee)\n3. Pickup Station (free)\n4. Company Pickup (free)"

def get_ask_address() -> str:
    return "Please drop your delivery address."

def get_delivery_confirmation_prompt(address: str, fee: float, total: float) -> str:
    return f"Delivery to {address} costs ₦{fee}. Your total including items is ₦{total}. Confirm delivery to {address}? (yes/no)"

def get_order_under_review(order_id: str, cart: list, delivery_fee: float, total: float, address: str) -> str:
    items_text = "\n".join([f"- {item['name']} x{item['quantity']}: ₦{item['price']*item['quantity']}" for item in cart])
    return f"Your order has been received and is under review.\n\nItems:\n{items_text}\nDelivery to: {address}\nDelivery fee: ₦{delivery_fee}\nTotal: ₦{total}\n\nOur sales team will confirm product availability shortly. You will receive a payment link once approved.\nOrder ID: {order_id}"

def get_payment_method_acknowledgment(method: str, order_id: str, total: float) -> str:
    if method == "cod":
        return f"Your order {order_id} (₦{total}) has been confirmed. Payment will be collected on delivery. Thank you!"
    elif method == "bank_transfer":
        return f"Send your payment receipt here after transfer.\n\nBank: Shortcaike Beauty Stores\nAccount: 0123456789\nBank Name: First Bank\nAmount: ₦{total}\nReference: {order_id}"
    return "Payment method selected. Please wait for confirmation."

def get_card_unavailable() -> str:
    return "Card payment is not yet available. Please choose Bank Transfer (1) or Cash on Delivery (3)."

def get_receipt_received() -> str:
    return "✅ Thank you for sending your payment receipt. Our sales team will verify it shortly. You will receive a confirmation once your payment is approved."

def get_payment_confirmation(order_id: str) -> str:
    return f"✅ Payment confirmed for order {order_id}.\n\nHere is your order ID: {order_id}\nYou can use this ID to track your delivery.\nYour order will be delivered to the address you provided.\nThank you for shopping with Shortcaike Beauty Stores!"

def get_tracking_response(order_id: str, status: str, address: str, eta: str = "", lat: float = None, lng: float = None) -> str:
    if status == "out_for_delivery":
        coords = f"{lat}, {lng}" if lat and lng else "unknown location"
        eta_text = f"Estimated delivery: {eta}" if eta else "Estimated delivery: Today within 2 hours"
        return f"Order ID: {order_id}\nStatus: Out for Delivery\nLocation: {coords}\n{eta_text}"
    elif status == "completed":
        return f"Order {order_id} has been delivered. Thank you for shopping with us!"
    else:
        return f"Order {order_id} is currently {status}. We'll notify you when it ships."

def get_order_not_found() -> str:
    return "Sorry, I couldn't find an order with that ID. Please check and try again."

def get_product_not_found_with_greeting(product: str, name: str = None) -> str:
    greet = f"Sorry {name}, " if name else "Sorry, "
    return greet + f"I couldn't find '{product}'. Please check the spelling or type 'products' to see our catalog."

def get_catalog_text(products: list) -> str:
    if not products:
        return "No products available at the moment."
    lines = ["Our products:"]
    for p in products:
        lines.append(f"{p['name']} – ₦{p['price']}")
    lines.append("\nTo order, say 'add 2 lipstick'.")
    return "\n".join(lines)

def get_skincare_advice(condition: str, fallback_product: str) -> str:
    advice = {
        "dry skin": "For dry skin, we recommend our Hydrating Serum. It contains hyaluronic acid to lock in moisture. Would you like me to add it to your cart?",
        "acne": "Our Acne Treatment Gel with tea tree oil is great for breakouts. Add to cart?",
        "oily skin": "Try our Oil Control Toner or the Acne Treatment Gel to manage excess sebum.",
        "sunburn": "For sunburn, we recommend our Aloe Vera Gel to soothe redness. Would you like to add it?",
        "redness": "Aloe Vera Gel calms irritated skin. Add to cart?",
    }
    return advice.get(condition.lower(), f"I recommend trying our {fallback_product}. Would you like more details?")

def get_cart_continued_confirmation() -> str:
    return "Continuing with your existing cart."

def get_cart_cleared_confirmation() -> str:
    return "Your cart has been cleared. You can now add new items."

def get_no_thanks_response(name: str) -> str:
    return f"Okay {name}, maybe next time. Feel free to ask about other products."

def get_complaint_logged() -> str:
    return "I'm sorry to hear that. Your complaint has been logged. Our customer care team will review it and contact you within 24 hours."

def get_usage_instructions(product: str) -> str:
    instructions = {
        "hydrating serum": "Apply a few drops to clean, dry face every morning and evening. Follow with moisturizer.",
        "brightening face cream": "Apply a small amount to clean, dry face every morning and evening. Avoid eye area. Use sunscreen during the day.",
        "acne treatment gel": "Apply thin layer to affected areas once daily. Start with every other day if you have sensitive skin.",
        "sunscreen spf 50": "Apply generously 15 minutes before sun exposure. Reapply every 2 hours.",
        "night repair cream": "Apply to clean skin before bedtime. Use after serum for best results.",
    }
    return instructions.get(product.lower(), "Please check the product label for instructions or contact our support.")

def get_greeting_with_cart_prompt(name: str, item_count: int, total: float) -> str:
    return f"Good evening, {name}. Welcome to Shortcaike Beauty Stores.\n\nYou have {item_count} item(s) in your cart from before (total ₦{total}). Would you like to continue with this cart or start a new one? Reply 'continue' or 'new'."

def get_default_reply() -> str:
    return "I'm not sure I understood. Could you tell me more about your skin concern or what you'd like to do? (e.g., 'I have dry skin', 'add serum to cart', 'checkout')"

def get_help_text() -> str:
    return """Here's how I can help:
- Ask about products for a skin concern (e.g., "What do you have for dry skin?")
- Add items to your cart (e.g., "add 2 lipstick" or "add face cream too")
- Review your cart ("show my cart")
- Proceed to checkout ("checkout")
- Clear your cart ("clear cart")
- Track an order ("track SBS-1234")
- Get product usage instructions ("how to use face cream")
- Report a complaint ("the serum burns my skin")

Just tell me what you need naturally – no need to memorise commands."""