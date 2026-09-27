from models.order import Order
from services import auth_service as auth

class PaymentService:
    def process(self):
        self.validate()
        auth.check()

    def validate(self):
        pass

def process_payment():
    pass
