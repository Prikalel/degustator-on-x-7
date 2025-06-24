# items_provider.py
import random

def get_random_item():
    # Example items, extend with real data and images as needed
    items = [
        {
            "name": "Glowing Mushroom",
            "visual": "Pulsating blue cap with yellow spots, emits soft hum",
            "cost": 50,
        },
        {
            "name": "Rocky Sludge",
            "visual": "Crystallized purple gel with embedded quartz fragments",
            "cost": 30
        },
    ]
    return random.choice(items)
