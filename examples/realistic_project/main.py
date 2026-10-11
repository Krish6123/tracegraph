from services.payment_service import PaymentService as PS
from services.payment_service import process_payment as charge
import services.payment_service as payment_module
from utils import database
from services import payment_service

def start():
    database.connect()
    
    # Class construction and simple object.method()
    service = PS()
    service.process()
    PS.process(service)
    payment_module.process_payment()
    payment_service.process_payment()
    charge()
    
    # Ambiguous method call - Nexus won't guess
    obj = get_random()
    obj.validate()

def get_random():
    pass

class Ambiguous:
    def validate(self):
        pass
