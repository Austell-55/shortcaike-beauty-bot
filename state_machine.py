from enum import Enum

class ConversationState(Enum):
    IDLE = 1
    AWAITING_NAME = 2
    AWAITING_CART_DECISION = 3
    AWAITING_DELIVERY_OPTION = 4
    AWAITING_ADDRESS = 5
    AWAITING_DELIVERY_CONFIRMATION = 6   # NEW: after address, waiting for yes/no
    AWAITING_PICKUP_STATION = 7
    AWAITING_COMPANY_NAME = 8
    AWAITING_PAYMENT_METHOD = 9
    AWAITING_RECEIPT = 10
    AWAITING_ADD_CONFIRMATION = 11      # after recommendation, waiting for yes/no
    AWAITING_COMPLAINT_DETAILS = 12     # optional, but we log directly

def state_to_string(state: ConversationState) -> str:
    mapping = {
        ConversationState.IDLE: "idle",
        ConversationState.AWAITING_NAME: "awaiting_name",
        ConversationState.AWAITING_CART_DECISION: "awaiting_cart_decision",
        ConversationState.AWAITING_DELIVERY_OPTION: "awaiting_delivery_option",
        ConversationState.AWAITING_ADDRESS: "awaiting_address",
        ConversationState.AWAITING_DELIVERY_CONFIRMATION: "awaiting_delivery_confirmation",
        ConversationState.AWAITING_PICKUP_STATION: "awaiting_pickup_station",
        ConversationState.AWAITING_COMPANY_NAME: "awaiting_company_name",
        ConversationState.AWAITING_PAYMENT_METHOD: "awaiting_payment_method",
        ConversationState.AWAITING_RECEIPT: "awaiting_receipt",
        ConversationState.AWAITING_ADD_CONFIRMATION: "awaiting_add_confirmation",
        ConversationState.AWAITING_COMPLAINT_DETAILS: "awaiting_complaint_details",
    }
    return mapping.get(state, "idle")

def string_to_state(state_str: str) -> ConversationState:
    mapping = {
        "idle": ConversationState.IDLE,
        "awaiting_name": ConversationState.AWAITING_NAME,
        "awaiting_cart_decision": ConversationState.AWAITING_CART_DECISION,
        "awaiting_delivery_option": ConversationState.AWAITING_DELIVERY_OPTION,
        "awaiting_address": ConversationState.AWAITING_ADDRESS,
        "awaiting_delivery_confirmation": ConversationState.AWAITING_DELIVERY_CONFIRMATION,
        "awaiting_pickup_station": ConversationState.AWAITING_PICKUP_STATION,
        "awaiting_company_name": ConversationState.AWAITING_COMPANY_NAME,
        "awaiting_payment_method": ConversationState.AWAITING_PAYMENT_METHOD,
        "awaiting_receipt": ConversationState.AWAITING_RECEIPT,
        "awaiting_add_confirmation": ConversationState.AWAITING_ADD_CONFIRMATION,
        "awaiting_complaint_details": ConversationState.AWAITING_COMPLAINT_DETAILS,
    }
    return mapping.get(state_str, ConversationState.IDLE)