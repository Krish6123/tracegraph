from services.payment_service import PaymentService


class Order:
    def settle(self):
        service = PaymentService()
        service.process()
