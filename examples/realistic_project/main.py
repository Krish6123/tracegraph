from services.payment_service import PaymentService as PS
from utils import database

def start():
    database.connect()
    
    # Class construction and simple object.method()
    service = PS()
    service.process()
    
    # Ambiguous method call - Nexus won't guess
    obj = get_random()
    obj.validate()

def get_random():
    pass

class Ambiguous:
    def validate(self):
        pass
