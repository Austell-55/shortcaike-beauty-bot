import json
import httpx
import re
from config import Config

OLLAMA_BASE_URL = Config.OLLAMA_BASE_URL
OLLAMA_MODEL = Config.OLLAMA_MODEL

async def call_ollama_intent(user_message: str, current_state: str = "idle", last_suggested_product: str = None, history: list = None) -> list:
    """
    Send user message to Ollama and return a list of actions.
    Handles natural language, typos, and extracts intent/entities.
    """
    # Build conversation history for context
    history_text = ""
    if history:
        for msg in history[-3:]:
            history_text += f"{msg['role']}: {msg['content']}\n"

    prompt = f"""You are a helpful customer assistant for Shortcaike Beauty Stores, a skincare and beauty products shop.
Your job is to understand the user's message and return ONLY a JSON object with the fields:
- "intent": one of the following:
    greeting, set_name, recommend, add_to_cart, add_extra_item, review_cart, checkout, continue, new_cart,
    delivery_option, set_address, confirm_delivery, set_pickup_station, set_payment_method, track_order,
    catalog, confirm_add, reject_add, complaint, usage_instruction, skincare_advice, help, unknown
- "entities": a dictionary with extra info (e.g., product_name, quantity, condition, address, etc.)

Important rules:
- The user may type with typos, misspellings, or natural phrases. Interpret their meaning.
- If they ask for a product recommendation based on a skin concern (dry skin, acne, sunburn, etc.), return "recommend" with the "concern" entity.
- If they ask for general skincare advice for a condition we may not have a product for (e.g., sunburn, dark circles, wrinkles), return "skincare_advice" with the "condition" entity.
- If they say "add face cream too" (no quantity), treat as "add_to_cart" with quantity=1.
- For "yes please" after a recommendation, return "confirm_add".
- For "no thanks", return "reject_add".
- For delivery options, map words "home", "express", "pickup", "company" to "delivery_option".
- For payment methods, map "bank", "cash", "card" to "set_payment_method".
- For tracking, if user provides an order ID (like SBS-1234), return "track_order".

Current conversation state: {current_state}
Last suggested product: {last_suggested_product}
Recent conversation:
{history_text}

User message: "{user_message}"

Return ONLY valid JSON. Example outputs:
{{"intent": "greeting"}}
{{"intent": "set_name", "entities": {{"name": "Sarah"}}}}
{{"intent": "recommend", "entities": {{"concern": "dry skin"}}}}
{{"intent": "skincare_advice", "entities": {{"condition": "sunburn"}}}}
{{"intent": "add_to_cart", "entities": {{"product_name": "hydrating serum", "quantity": 1}}}}
{{"intent": "review_cart"}}
{{"intent": "checkout"}}
{{"intent": "delivery_option", "entities": {{"delivery_type": "home"}}}}
{{"intent": "set_address", "entities": {{"address": "15 Bishop Street, Ikeja"}}}}
{{"intent": "confirm_delivery", "entities": {{"confirmed": true}}}}
{{"intent": "set_payment_method", "entities": {{"method": "bank"}}}}
{{"intent": "track_order", "entities": {{"order_id": "SBS-1234"}}}}
{{"intent": "catalog"}}
{{"intent": "confirm_add"}}
{{"intent": "reject_add"}}
{{"intent": "complaint", "entities": {{"complaint_text": "the serum burns my skin"}}}}
{{"intent": "usage_instruction", "entities": {{"product": "face cream"}}}}
{{"intent": "help"}}
"""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}
            )
            result = response.json()
            raw = result.get("response", "").strip()
            # Remove markdown if present
            if raw.startswith("```json"):
                raw = raw.split("```json")[1].split("```")[0]
            elif raw.startswith("```"):
                raw = raw.split("```")[1].split("```")[0]
            data = json.loads(raw)
            intent = data.get("intent", "unknown")
            entities = data.get("entities", {})
            # Convert to list of actions
            actions = []
            if intent == "greeting":
                actions.append({"action": "greeting"})
            elif intent == "set_name":
                name = entities.get("name", "")
                if name:
                    actions.append({"action": "set_name", "name": name})
            elif intent == "recommend":
                condition = entities.get("concern", "")
                if condition:
                    actions.append({"action": "recommend", "condition": condition})
            elif intent == "skincare_advice":
                condition = entities.get("condition", "")
                if condition:
                    actions.append({"action": "skincare_advice", "condition": condition})
            elif intent == "add_to_cart":
                product = entities.get("product_name", "")
                qty = entities.get("quantity", 1)
                if product:
                    actions.append({"action": "add_to_cart", "product": product, "quantity": qty})
            elif intent == "add_extra_item":
                product = entities.get("product_name", "")
                if product:
                    actions.append({"action": "add_to_cart", "product": product, "quantity": 1})
            elif intent == "review_cart":
                actions.append({"action": "show_cart"})
            elif intent == "checkout":
                actions.append({"action": "checkout"})
            elif intent == "continue":
                actions.append({"action": "continue_cart"})
            elif intent == "new_cart":
                actions.append({"action": "new_cart"})
            elif intent == "delivery_option":
                delivery_type = entities.get("delivery_type", "")
                if delivery_type in ["home", "express", "pickup", "company"]:
                    actions.append({"action": "set_delivery_option", "option": delivery_type + "_delivery" if delivery_type in ["home","express"] else delivery_type})
            elif intent == "set_address":
                address = entities.get("address", "")
                if address:
                    actions.append({"action": "set_address", "address": address})
            elif intent == "confirm_delivery":
                confirmed = entities.get("confirmed", False)
                actions.append({"action": "confirm_delivery", "confirmed": confirmed})
            elif intent == "set_pickup_station":
                station = entities.get("station_name", "")
                if station:
                    actions.append({"action": "set_pickup_station", "station": station})
            elif intent == "set_payment_method":
                method = entities.get("method", "")
                if method in ["bank", "cod", "card"]:
                    actions.append({"action": "set_payment_method", "method": method})
            elif intent == "track_order":
                order_id = entities.get("order_id", "")
                if order_id:
                    actions.append({"action": "track_order", "order_id": order_id})
            elif intent == "catalog":
                actions.append({"action": "catalog"})
            elif intent == "confirm_add":
                actions.append({"action": "confirm_add"})
            elif intent == "reject_add":
                actions.append({"action": "reject_add"})
            elif intent == "complaint":
                complaint_text = entities.get("complaint_text", user_message)
                actions.append({"action": "complaint", "complaint_text": complaint_text})
            elif intent == "usage_instruction":
                product = entities.get("product", "")
                if product:
                    actions.append({"action": "usage_instruction", "product": product})
            elif intent == "help":
                actions.append({"action": "help"})
            else:
                return []
            return actions
    except Exception as e:
        print(f"Ollama error: {e}")
        # Fallback regex for basic commands (so bot works even without Ollama)
        msg = user_message.lower().strip()
        if msg in ["good evening", "good morning", "good afternoon", "hello", "hi", "hey"]:
            return [{"action": "greeting"}]
        if re.search(r'my name is (\w+)', msg):
            name = re.search(r'my name is (\w+)', msg).group(1)
            return [{"action": "set_name", "name": name}]
        if any(phrase in msg for phrase in ["products", "catalog"]):
            return [{"action": "catalog"}]
        if any(phrase in msg for phrase in ["cart", "my cart", "review cart"]):
            return [{"action": "show_cart"}]
        if any(phrase in msg for phrase in ["checkout", "pay now"]):
            return [{"action": "checkout"}]
        if any(phrase in msg for phrase in ["clear cart", "empty cart"]):
            return [{"action": "clear_cart"}]
        if re.search(r'track\s+(\w+-\d+)', msg):
            order_id = re.search(r'track\s+(\w+-\d+)', msg).group(1)
            return [{"action": "track_order", "order_id": order_id}]
        if "help" in msg:
            return [{"action": "help"}]
        # For skincare advice (fallback if no product)
        if any(word in msg for word in ["dry skin", "acne", "sunburn", "oily", "redness"]):
            condition = "dry skin" if "dry" in msg else "acne" if "acne" in msg else "sunburn" if "sun" in msg else "unknown"
            return [{"action": "skincare_advice", "condition": condition}]
        return []