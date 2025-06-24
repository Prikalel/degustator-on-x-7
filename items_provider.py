# items_provider.py
import random

def get_random_item():
    # Example items, extend with real data and images as needed
    items = [
        {
            "name": "Светящийся гриб",
            "image": "mushroom.png",
            "cost": 50,
        },
        {
            "name": "Фиолетовый гель",
            "image": "poition.png",
            "cost": 30
        },
    ]
    return random.choice(items)
