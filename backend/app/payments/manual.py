from . import PaymentProvider, PaymentInfo


class ManualProvider(PaymentProvider):
    name = "manual"

    async def create(self, user_id: int, amount: int, plan: str) -> PaymentInfo:
        return PaymentInfo(
            provider=self.name,
            external_id="",
            status="pending",
            instructions="Оплата подтверждается вручную администратором. "
                         "Дождитесь уведомления об активации.",
        )