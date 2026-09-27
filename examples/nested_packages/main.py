from models.order import Order
from services import payment_service
from services.payment_service import PaymentService
from services.payment_service import PaymentService as PS
from services.payment_service import process_payment
import services.payment_service
import services.payment_service as payment_mod


def checkout():
    service = PaymentService()
    service.process()
    PaymentService.process(service)
    process_payment()
    payment_mod.process_payment()
    payment_service.process_payment()
    aliased = PS()
    aliased.process()
    services.payment_service.process_payment()


def run_order():
    order = Order()
    order.settle()


def ambiguous_driver(obj):
    # Receiver type is unknown. Nexus must not guess every process() method.
    obj.process()
