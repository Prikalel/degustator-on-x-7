# items_provider.py
import random

# Predefined list of items for testing
items = [
    {"name": "Гриб: Красный кристалл", "cost": 50},
    {"name": "Гриб: Синий пузырь", "cost": 100},
    {"name": "Камень: Зеленый осколок", "cost": 150},
    {"name": "Жидкость: Фиолетовый нектар", "cost": 200},
    {"name": "Растение: Желтый корень", "cost": 75},
    {"name": "Гриб: Серебристая шляпка", "cost": 125},
    {"name": "Камень: Прозрачный куб", "cost": 175},
    {"name": "Жидкость: Оранжевый гель", "cost": 90},
]

def get_random_item():
    """Return a random item from scripts.the predefined list."""
    item = random.choice(items).copy()  # Make a copy to avoid modifying original
    # For testing purposes, we'll use a placeholder image
    item["assets/images/image"] = "in-game-background.png"  # Using existing image as placeholder
    return item