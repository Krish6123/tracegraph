def save_payment():
    return True


def process_payment():
    save_payment()
    return True


class PaymentService:
    def process(self):
        self.validate()
        save_payment()

    def validate(self):
        return True
