PLANS = {
    "month": {"name": "1 месяц", "days": 30, "price": 299},
    "3months": {"name": "3 месяца", "days": 90, "price": 799},
    "year": {"name": "12 месяцев", "days": 365, "price": 2499},
}


class PaymentInfo:
    def __init__(self, provider: str, external_id: str, status: str, instructions: str):
        self.provider = provider
        self.external_id = external_id
        self.status = status
        self.instructions = instructions


class PaymentProvider:
    name = "base"

    async def create(self, user_id: int, amount: int, plan: str) -> PaymentInfo:
        raise NotImplementedError

    async def handle_webhook(self, payload: dict) -> tuple[str, int] | None:
        return None


def get_provider(name: str) -> PaymentProvider:
    from .manual import ManualProvider
    providers = {"manual": ManualProvider()}
    return providers.get(name, ManualProvider())