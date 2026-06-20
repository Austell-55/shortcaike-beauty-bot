import json
import re
import httpx
import sqlite3
from datetime import datetime, timezone, timedelta
from fastapi import Request
from fastapi.responses import JSONResponse

from config import Config
from session_manager import get_session, update_session
from state_machine import ConversationState, state_to_string
from ollama_client import call_ollama_intent
from cart import get_user_cart, add_to_cart, remove_from_cart, clear_cart, get_cart_total
from products import get_catalog
from orders import create_order, update_order_status, get_order_by_id
from delivery import get_delivery_fee_by_location, get_all_pickup_stations, get_pickup_station_by_name
from templates import *

WHATSAPP_TOKEN = Config.WHATSAPP_ACCESS_TOKEN
WHATSAPP_PHONE_NUMBER_ID = Config.WHATSAPP_PHONE_NUMBER_ID

processed_message_ids = set()

# ========== Advice Dictionary ==========
SKINCARE_ADVICE = {
    "sunburn": {
        "advice": "wear a face cap when outside, drink enough water, and always check product expiry dates",
        "related_product": "Aloe Vera Gel",
        "benefit": "soothe redness"
    },
    "dark circles": {
        "advice": "get enough sleep, stay hydrated, and use a gentle eye cream",
        "related_product": "Eye Repair Cream",
        "benefit": "brighten under‑eyes"
    },
    "wrinkles": {
        "advice": "use sunscreen daily, moisturise, and avoid smoking",
        "related_product": "Hydrating Serum",
        "benefit": "plump skin"
    },
    "oily skin": {
        "advice": "wash your face twice a day, use oil‑free products, and avoid touching your face",
        "related_product": "Acne Treatment Gel",
        "benefit": "control excess oil"
    },
    "redness": {
        "advice": "avoid harsh products, use gentle cleansers, and protect your skin from the sun",
        "related_product": "Aloe Vera Gel",
        "benefit": "calm irritation"
    },
    "dry skin": {
        "advice": "moisturise daily, use a humidifier, and avoid hot showers",
        "related_product": "Hydrating Serum",
        "benefit": "lock in moisture"
    }
}

async def send_whatsapp(to: str, message: str):
    if not message or not message.strip():
        print("Empty message, skipping")
        return
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    data = {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": message[:4096]}}
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=data, headers=headers)
                print(f"WhatsApp send status: {resp.status_code}")
                return
        except Exception as e:
            print(f"Attempt {attempt+1} failed: {e}")
            if attempt == 2:
                print("Failed to send WhatsApp message after 3 attempts")

def save_message(user_id: str, role: str, content: str):
    conn = sqlite3.connect("messages.db")
    c = conn.cursor()
    try:
        c.execute("INSERT INTO messages (user_id, role, content, timestamp) VALUES (?,?,?,?)",
                  (user_id, role, content, datetime.now(timezone.utc).isoformat()))
    except sqlite3.OperationalError as e:
        if "no such column" in str(e):
            c.execute("ALTER TABLE messages ADD COLUMN user_id TEXT")
            c.execute("ALTER TABLE messages ADD COLUMN role TEXT")
            c.execute("ALTER TABLE messages ADD COLUMN content TEXT")
            c.execute("ALTER TABLE messages ADD COLUMN timestamp TIMESTAMP")
            conn.commit()
            c.execute("INSERT INTO messages (user_id, role, content, timestamp) VALUES (?,?,?,?)",
                      (user_id, role, content, datetime.now(timezone.utc).isoformat()))
        else:
            raise
    conn.commit()
    conn.close()

def get_recent_messages(user_id: str, limit: int = 5):
    conn = sqlite3.connect("messages.db")
    c = conn.cursor()
    try:
        c.execute("SELECT role, content FROM messages WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?", (user_id, limit))
        rows = c.fetchall()
    except sqlite3.OperationalError:
        rows = []
    conn.close()
    return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

def store_customer_name(phone: str, name: str):
    conn = sqlite3.connect("messages.db")
    c = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    c.execute("""
        INSERT OR REPLACE INTO customers (phone_number, name, first_seen, last_seen)
        VALUES (?, ?, COALESCE((SELECT first_seen FROM customers WHERE phone_number=?), ?), ?)
    """, (phone, name, phone, now, now))
    conn.commit()
    conn.close()

def log_to_audit(user_id: str, action: str, details: str):
    conn = sqlite3.connect("messages.db")
    c = conn.cursor()
    c.execute("INSERT INTO audit_logs (user_username, action, details, timestamp) VALUES (?, ?, ?, ?)",
              (user_id, action, details, datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()

async def execute_actions(user_id: str, actions: list) -> str:
    session = get_session(user_id)
    final_reply = ""
    for action in actions:
        act = action.get("action")
        if act == "greeting":
            final_reply = get_greeting(session.get("customer_name"))
            update_session(user_id, step=state_to_string(ConversationState.IDLE))
        elif act == "set_name":
            name = action.get("name", "").strip()
            if name:
                store_customer_name(user_id, name)
                update_session(user_id, customer_name=name, step=state_to_string(ConversationState.IDLE))
                final_reply = get_name_acknowledgment(name)
        elif act == "recommend":
            condition = action.get("condition", "").lower()
            product_map = {
                "dry skin": {"name": "Hydrating Serum", "price": 7000, "desc": "Contains hyaluronic acid which locks in moisture"},
                "acne": {"name": "Acne Treatment Gel", "price": 4500, "desc": "Tea tree oil based to clear breakouts"},
                "brightening": {"name": "Brightening Face Cream", "price": 5500, "desc": "Even skin tone and reduce dark spots"},
                "sunburn": {"name": "Sunscreen SPF 50", "price": 6000, "desc": "Broad spectrum UVA/UVB protection, soothes redness"},
                "redness": {"name": "Aloe Vera Gel", "price": 3500, "desc": "Calms irritated skin"},
                "exfoliate": {"name": "Exfoliating Scrub", "price": 4000, "desc": "Gentle exfoliation for smooth skin"},
                "night repair": {"name": "Night Repair Cream", "price": 8000, "desc": "Deep hydration while you sleep"},
            }
            product = product_map.get(condition)
            if product:
                final_reply = get_recommendation(product["name"], product["price"], product["desc"], condition)
                update_session(user_id, last_suggested_product=product["name"], step=state_to_string(ConversationState.AWAITING_ADD_CONFIRMATION))
            else:
                final_reply = get_skincare_advice(condition, "Aloe Vera Gel")
        elif act == "skincare_advice":
            condition = action.get("condition", "").lower()
            advice_data = SKINCARE_ADVICE.get(condition)
            name = session.get("customer_name", "there")
            if advice_data:
                advice_text = advice_data["advice"]
                product_name = advice_data["related_product"]
                benefit = advice_data["benefit"]
                conn = sqlite3.connect("messages.db")
                c = conn.cursor()
                c.execute("SELECT price FROM products WHERE LOWER(name) = ?", (product_name.lower(),))
                row = c.fetchone()
                price = row[0] if row else 0
                conn.close()
                final_reply = f"I'm sorry to hear that, {name}. For {condition}, I recommend you {advice_text}. We don't have a dedicated product for {condition}, but our {product_name} can help {benefit}. Would you like to add it to your cart?"
                update_session(user_id, last_suggested_product=product_name, step=state_to_string(ConversationState.AWAITING_ADD_CONFIRMATION))
            else:
                final_reply = f"I'm sorry to hear that, {name}. For {condition}, I recommend wearing protective clothing, staying hydrated, and checking product expiry dates. We may not have a product for this right now, but feel free to ask about other concerns."
        elif act == "add_to_cart":
            product = action.get("product")
            qty = action.get("quantity", 1)
            if product and add_to_cart(user_id, product, qty):
                if qty == 1:
                    final_reply = get_add_to_cart_confirmation(product)
                else:
                    final_reply = f"{qty} x {product} added to your cart. You can ask me to review your cart anytime."
                update_session(user_id, step=state_to_string(ConversationState.IDLE))
            else:
                final_reply = get_product_not_found_with_greeting(product, session.get("customer_name"))
        elif act == "remove_from_cart":
            product = action.get("product")
            if product and remove_from_cart(user_id, product, action.get("quantity")):
                final_reply = get_remove_confirmation(product)
            else:
                final_reply = f"{product} is not in your cart."
        elif act == "show_cart":
            cart = get_user_cart(user_id)
            # Ensure each item has a 'name' key (cart may store product under 'product' or 'product_name')
            normalized_cart = []
            for item in cart:
                if 'name' not in item:
                    if 'product' in item:
                        item['name'] = item['product']
                    elif 'product_name' in item:
                        item['name'] = item['product_name']
                    else:
                        # fallback: take first string value as name
                        for k, v in item.items():
                            if isinstance(v, str):
                                item['name'] = v
                                break
                normalized_cart.append(item)
            total = get_cart_total(user_id)
            final_reply = get_show_cart(normalized_cart, total)
        elif act == "clear_cart":
            clear_cart(user_id)
            final_reply = get_clear_cart_confirmation()
        elif act == "checkout":
            if not get_user_cart(user_id):
                final_reply = "Your cart is empty. Add some products first."
            else:
                update_session(user_id, step=state_to_string(ConversationState.AWAITING_DELIVERY_OPTION))
                final_reply = get_delivery_options()
        elif act == "set_delivery_option":
            option = action.get("option")
            valid = ["home_delivery", "express_delivery", "pickup_station", "company_pickup"]
            if option in valid:
                update_session(user_id, delivery_option=option)
                if option in ["pickup_station", "company_pickup"]:
                    stations = get_all_pickup_stations()
                    final_reply = get_pickup_stations(stations)
                    update_session(user_id, step=state_to_string(ConversationState.AWAITING_PICKUP_STATION))
                else:
                    update_session(user_id, step=state_to_string(ConversationState.AWAITING_ADDRESS))
                    final_reply = get_ask_address()
            else:
                final_reply = "Please choose a valid option: 1, 2, 3, or 4."
        elif act == "set_address":
            address = action.get("address")
            if address:
                fee = get_delivery_fee_by_location(address) if session.get("delivery_option") in ["home_delivery","express_delivery"] else 0
                cart_total = get_cart_total(user_id)
                total = cart_total + fee
                update_session(user_id, temp_address=address, temp_delivery_fee=fee, temp_total=total, step="awaiting_delivery_confirmation")
                final_reply = f"Delivery to {address} costs ₦{fee}. Your total including items is ₦{total}. Confirm delivery to {address}? (yes/no)"
            else:
                final_reply = "Please provide a valid delivery address."
        elif act == "confirm_delivery":
            if action.get("confirmed"):
                address = session.get("temp_address")
                fee = session.get("temp_delivery_fee")
                total = session.get("temp_total")
                cart = get_user_cart(user_id)
                delivery_option = session.get("delivery_option", "home_delivery")
                # ✅ CHANGED: status changed from "pending_payment" to "pending_availability" so sales dashboard sees it
                order_id = create_order(user_id, cart, address, delivery_option, session.get("customer_name", ""), user_id, status="pending_availability")
                update_session(user_id, pending_order_id=order_id, step="awaiting_payment_method")
                items_text = "\n".join([f"- {item.get('name', item.get('product', 'unknown'))} x{item['quantity']}: ₦{item['price']*item['quantity']}" for item in cart])
                invoice = f"Here is your invoice:\n{items_text}\nDelivery: ₦{fee}\nTotal: ₦{total}"
                final_reply = invoice + "\n\nHow would you like to pay?\n1. Bank Transfer\n2. Card Payment\n3. Cash on Delivery"
            else:
                final_reply = "Please provide a different address or choose another delivery option."
                update_session(user_id, step="awaiting_delivery_option")
        elif act == "set_payment_method":
            method = action.get("method")
            order_id = session.get("pending_order_id")
            if not order_id:
                final_reply = "Please start a checkout first."
            else:
                order = get_order_by_id(order_id)
                if order:
                    update_session(user_id, payment_method=method)
                    if method == "cod":
                        update_order_status(order_id, "ready_for_delivery")
                        final_reply = get_payment_method_acknowledgment("cod", order_id, order["total"])
                        clear_cart(user_id)
                        update_session(user_id, step=state_to_string(ConversationState.IDLE))
                    elif method == "bank_transfer":
                        update_order_status(order_id, "awaiting_payment")
                        final_reply = get_payment_method_acknowledgment("bank_transfer", order_id, order["total"])
                        update_session(user_id, step="awaiting_receipt")
                    elif method == "card":
                        final_reply = get_card_unavailable()
                    else:
                        final_reply = "Invalid payment method."
                else:
                    final_reply = "Order not found."
        elif act == "track_order":
            order_id = action.get("order_id")
            if order_id:
                order = get_order_by_id(order_id)
                if order:
                    final_reply = get_tracking_response(order_id, order["status"], order.get("address",""), order.get("eta",""), order.get("gps_lat"), order.get("gps_lng"))
                else:
                    final_reply = get_order_not_found()
            else:
                final_reply = "Please provide an order ID (e.g., SBS-1234)."
        elif act == "catalog":
            final_reply = get_catalog_text(get_catalog())
        elif act == "confirm_add":
            product = action.get("product") or session.get("last_suggested_product")
            qty = action.get("quantity", 1)
            if product:
                add_to_cart(user_id, product, qty)
                if qty == 1:
                    final_reply = get_add_to_cart_confirmation(product)
                else:
                    final_reply = f"{qty} x {product} added to your cart. You can ask me to review your cart anytime."
                update_session(user_id, step=state_to_string(ConversationState.IDLE))
            else:
                final_reply = "Sorry, I'm not sure what product you want to add."
        elif act == "reject_add":
            final_reply = get_no_thanks_response(session.get("customer_name", "there"))
            update_session(user_id, step=state_to_string(ConversationState.IDLE))
        elif act == "complaint":
            complaint_text = action.get("complaint_text", "")
            log_to_audit(user_id, "COMPLAINT", complaint_text)
            final_reply = get_complaint_logged()
            update_session(user_id, step=state_to_string(ConversationState.IDLE))
        elif act == "usage_instruction":
            product = action.get("product", "").lower()
            instructions = {
                "hydrating serum": "Apply a few drops to clean, dry face every morning and evening. Follow with moisturizer.",
                "brightening face cream": "Apply a small amount to clean, dry face every morning and evening. Avoid eye area. Use sunscreen during the day.",
                "acne treatment gel": "Apply thin layer to affected areas once daily. Start with every other day if you have sensitive skin.",
                "sunscreen spf 50": "Apply generously 15 minutes before sun exposure. Reapply every 2 hours.",
                "night repair cream": "Apply to clean skin before bedtime. Use after serum for best results.",
                "aloe vera gel": "Apply a thin layer to affected area. Can be used daily.",
            }
            reply = instructions.get(product, "Please check the product label for instructions or contact our support.")
            final_reply = reply
        elif act == "continue_cart":
            final_reply = get_cart_continued_confirmation()
            update_session(user_id, step=state_to_string(ConversationState.IDLE), cart_prompt_sent=False)
        elif act == "new_cart":
            clear_cart(user_id)
            final_reply = get_cart_cleared_confirmation()
            update_session(user_id, step=state_to_string(ConversationState.IDLE), cart_prompt_sent=False)
        elif act == "help":
            final_reply = get_help_text()
        else:
            final_reply = get_default_reply()
    if not final_reply:
        final_reply = get_default_reply()
    return final_reply

async def handle_whatsapp(request: Request):
    global processed_message_ids
    try:
        data = await request.json()
        messages = data.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {}).get("messages", [])
        if not messages:
            return JSONResponse({"status": "ok"})
        msg = messages[0]
        msg_id = msg.get("id")
        if msg_id in processed_message_ids:
            print(f"Ignored duplicate message: {msg_id}")
            return JSONResponse({"status": "ok"})
        processed_message_ids.add(msg_id)
        if len(processed_message_ids) > 1000:
            processed_message_ids = set(list(processed_message_ids)[-500:])
        user_id = msg["from"]
        if msg.get("type") == "image":
            await send_whatsapp(user_id, get_receipt_received())
            save_message(user_id, "user", "[Image receipt]")
            save_message(user_id, "assistant", get_receipt_received())
            return JSONResponse({"status": "ok"})
        if msg.get("type") != "text":
            return JSONResponse({"status": "ok"})
        user_text = msg["text"]["body"]
        save_message(user_id, "user", user_text)

        session = get_session(user_id)
        current_state = session.get("step", "idle")

        # ========== 1. EXPLICIT GREETING DETECTION ==========
        lower_text = user_text.lower().strip()
        if lower_text in ["good evening", "good morning", "good afternoon", "hello", "hi", "hey"]:
            if session.get("customer_name"):
                reply = f"Good evening {session['customer_name']}! Welcome back. How can I help you today?"
                await send_whatsapp(user_id, reply)
                save_message(user_id, "assistant", reply)
                update_session(user_id, step=state_to_string(ConversationState.IDLE), cart_prompt_sent=False)
            else:
                reply = "Good morning! I'm the Shortcaike Beauty assistant. What's your name?"
                await send_whatsapp(user_id, reply)
                save_message(user_id, "assistant", reply)
                update_session(user_id, step="awaiting_name")
            return JSONResponse({"status": "ok"})

        # ========== 2. HANDLE AWAITING_NAME STATE ==========
        if current_state == "awaiting_name":
            name = user_text.strip()
            if name and len(name) > 1:
                store_customer_name(user_id, name)
                update_session(user_id, customer_name=name, step=state_to_string(ConversationState.IDLE))
                reply = f"Nice to meet you, {name}. Welcome to Shortcaike Beauty Stores, where beauty is our priority. Feel free to ask me anything about our products or skincare."
                await send_whatsapp(user_id, reply)
                save_message(user_id, "assistant", reply)
            else:
                reply = "Please tell me your name (e.g., 'Sarah')."
                await send_whatsapp(user_id, reply)
                save_message(user_id, "assistant", reply)
            return JSONResponse({"status": "ok"})

        # ========== 3. DIRECT COMMANDS ==========
        lower_text = user_text.lower()

        # Products / catalog
        if any(phrase in lower_text for phrase in ["products", "catalog", "catalogue", "product list", "show products", "see products", "view catalog"]):
            actions = [{"action": "catalog"}]
            reply = await execute_actions(user_id, actions)
            await send_whatsapp(user_id, reply)
            save_message(user_id, "assistant", reply)
            return JSONResponse({"status": "ok"})

        # Show cart
        if any(phrase in lower_text for phrase in ["show cart", "review cart", "view my cart", "what's in my cart", "my cart", "cart"]):
            actions = [{"action": "show_cart"}]
            reply = await execute_actions(user_id, actions)
            await send_whatsapp(user_id, reply)
            save_message(user_id, "assistant", reply)
            return JSONResponse({"status": "ok"})

        # Checkout
        if any(phrase in lower_text for phrase in ["checkout", "check out", "proceed to checkout", "pay now"]):
            if current_state != "awaiting_cart_decision":
                actions = [{"action": "checkout"}]
                reply = await execute_actions(user_id, actions)
                await send_whatsapp(user_id, reply)
                save_message(user_id, "assistant", reply)
                return JSONResponse({"status": "ok"})

        # Clear cart
        if any(phrase in lower_text for phrase in ["clear cart", "empty cart"]):
            actions = [{"action": "clear_cart"}]
            reply = await execute_actions(user_id, actions)
            await send_whatsapp(user_id, reply)
            save_message(user_id, "assistant", reply)
            return JSONResponse({"status": "ok"})

        # Help
        if any(phrase in lower_text for phrase in ["help", "commands"]):
            actions = [{"action": "help"}]
            reply = await execute_actions(user_id, actions)
            await send_whatsapp(user_id, reply)
            save_message(user_id, "assistant", reply)
            return JSONResponse({"status": "ok"})

        # Track order
        track_match = re.search(r'track\s+(\w+-\d+)', lower_text)
        if track_match:
            order_id = track_match.group(1)
            actions = [{"action": "track_order", "order_id": order_id}]
            reply = await execute_actions(user_id, actions)
            await send_whatsapp(user_id, reply)
            save_message(user_id, "assistant", reply)
            return JSONResponse({"status": "ok"})

        # ========== BULK ORDER DETECTION (with word numbers) ==========
        if re.search(r'\b(?:add|get|buy|order)\b', lower_text):
            processed_text = lower_text
            word_to_num = {
                "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
                "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10"
            }
            for word, num in word_to_num.items():
                processed_text = re.sub(rf'\b{word}\b', num, processed_text)
            parts = re.split(r'\s+and\s+', processed_text)
            items = []
            for part in parts:
                match = re.search(r'(\d+)\s+([a-zA-Z\s]+)$', part)
                if not match:
                    match = re.search(r'\b(\d+)\s+([a-zA-Z\s]+)$', part)
                if match:
                    qty = int(match.group(1))
                    prod = match.group(2).strip()
                    items.append((qty, prod))
            if items:
                added = []
                for qty, prod in items:
                    if add_to_cart(user_id, prod, qty):
                        added.append(f"{qty} x {prod}")
                if added:
                    reply = f"Added {', '.join(added)} to your cart. Type 'cart' to review or 'checkout' to order."
                    update_session(user_id, cart_prompt_sent=True)
                else:
                    reply = "Sorry, I couldn't add one or more products. Please check the names."
                await send_whatsapp(user_id, reply)
                save_message(user_id, "assistant", reply)
                return JSONResponse({"status": "ok"})

        # ========== STATE-SPECIFIC HANDLING ==========
        if current_state == "awaiting_cart_decision":
            if user_text.lower() in ["continue", "cont", "c", "continue shopping"]:
                reply = get_cart_continued_confirmation()
                update_session(user_id, step=state_to_string(ConversationState.IDLE), cart_prompt_sent=False)
                await send_whatsapp(user_id, reply)
                save_message(user_id, "assistant", reply)
                return JSONResponse({"status": "ok"})
            elif user_text.lower() in ["new", "n"]:
                clear_cart(user_id)
                reply = get_cart_cleared_confirmation()
                update_session(user_id, step=state_to_string(ConversationState.IDLE), cart_prompt_sent=False)
                await send_whatsapp(user_id, reply)
                save_message(user_id, "assistant", reply)
                return JSONResponse({"status": "ok"})

        if current_state == "awaiting_delivery_option":
            lower = user_text.lower()
            if lower == "1" or "home" in lower or "home delivery" in lower:
                actions = [{"action": "set_delivery_option", "option": "home_delivery"}]
            elif lower == "2" or "express" in lower:
                actions = [{"action": "set_delivery_option", "option": "express_delivery"}]
            elif lower == "3" or "pickup" in lower:
                actions = [{"action": "set_delivery_option", "option": "pickup_station"}]
            elif lower == "4" or "company" in lower:
                actions = [{"action": "set_delivery_option", "option": "company_pickup"}]
            else:
                actions = None
            if actions:
                reply = await execute_actions(user_id, actions)
                await send_whatsapp(user_id, reply)
                save_message(user_id, "assistant", reply)
                return JSONResponse({"status": "ok"})

        if current_state == "awaiting_address":
            address = user_text.strip()
            if address:
                fee = get_delivery_fee_by_location(address) if session.get("delivery_option") in ["home_delivery","express_delivery"] else 0
                cart_total = get_cart_total(user_id)
                total = cart_total + fee
                update_session(user_id, temp_address=address, temp_delivery_fee=fee, temp_total=total, step="awaiting_delivery_confirmation")
                reply = f"Delivery to {address} costs ₦{fee}. Your total including items is ₦{total}. Confirm delivery to {address}? (yes/no)"
                await send_whatsapp(user_id, reply)
                save_message(user_id, "assistant", reply)
            else:
                reply = "Please provide a valid address."
                await send_whatsapp(user_id, reply)
                save_message(user_id, "assistant", reply)
            return JSONResponse({"status": "ok"})

        if current_state == "awaiting_delivery_confirmation":
            if user_text.lower() in ["yes", "y", "confirm"]:
                actions = [{"action": "confirm_delivery", "confirmed": True}]
                reply = await execute_actions(user_id, actions)
                await send_whatsapp(user_id, reply)
                save_message(user_id, "assistant", reply)
            else:
                actions = [{"action": "confirm_delivery", "confirmed": False}]
                reply = await execute_actions(user_id, actions)
                await send_whatsapp(user_id, reply)
                save_message(user_id, "assistant", reply)
            return JSONResponse({"status": "ok"})

        if current_state == "awaiting_pickup_station":
            lower = user_text.lower()
            station_map = {
                "ikeja": "Ikeja Station",
                "lekki": "Lekki Station",
                "surulere": "Surulere Station",
                "vi": "VI Station",
                "victoria island": "VI Station",
                "1": "Ikeja Station",
                "2": "Lekki Station",
                "3": "Surulere Station",
                "4": "VI Station",
            }
            station_name = None
            for key in station_map:
                if key in lower:
                    station_name = station_map[key]
                    break
            if station_name:
                actions = [{"action": "set_pickup_station", "station": station_name}]
                reply = await execute_actions(user_id, actions)
                await send_whatsapp(user_id, reply)
                save_message(user_id, "assistant", reply)
            else:
                stations = get_all_pickup_stations()
                reply = get_pickup_stations(stations)
                await send_whatsapp(user_id, reply)
                save_message(user_id, "assistant", reply)
            return JSONResponse({"status": "ok"})

        if current_state == "awaiting_payment_method":
            lower = user_text.lower()
            if any(w in lower for w in ["1", "bank", "transfer"]):
                method = "bank_transfer"
            elif any(w in lower for w in ["3", "cash", "cod", "delivery"]):
                method = "cod"
            elif any(w in lower for w in ["2", "card"]):
                method = "card"
            else:
                method = None
            if method:
                actions = [{"action": "set_payment_method", "method": method}]
                reply = await execute_actions(user_id, actions)
                await send_whatsapp(user_id, reply)
                save_message(user_id, "assistant", reply)
            else:
                reply = "Please choose a valid payment method: 1 (Bank Transfer), 2 (Card), or 3 (Cash on Delivery)."
                await send_whatsapp(user_id, reply)
                save_message(user_id, "assistant", reply)
            return JSONResponse({"status": "ok"})

        # ========== CART REMINDER ==========
        cart = get_user_cart(user_id)
        if current_state == "idle" and cart and not session.get("cart_prompt_sent"):
            name = session.get("customer_name")
            if name:
                total = get_cart_total(user_id)
                total_quantity = sum(item['quantity'] for item in cart)
                reply = get_greeting_with_cart_prompt(name, total_quantity, total)
                await send_whatsapp(user_id, reply)
                save_message(user_id, "assistant", reply)
                update_session(user_id, step=state_to_string(ConversationState.AWAITING_CART_DECISION), cart_prompt_sent=True)
                return JSONResponse({"status": "ok"})

        # ========== OLLAMA FALLBACK ==========
        last_suggested = session.get("last_suggested_product")
        history = get_recent_messages(user_id, limit=5)
        actions = await call_ollama_intent(user_text, current_state, last_suggested, history)

        if not actions:
            reply = "I'm not sure I understood. Could you tell me more about your skin concern or what you'd like to do? (e.g., 'I have dry skin', 'add serum to cart', 'checkout')"
        else:
            reply = await execute_actions(user_id, actions)

        await send_whatsapp(user_id, reply)
        save_message(user_id, "assistant", reply)
        return JSONResponse({"status": "ok"})

    except Exception as e:
        print(f"Webhook error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=500)