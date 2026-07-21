from scripts.enum import Enum
import random

class Effect(Enum):
    Food = 1
    Toxic = 2

def get_random_effect():
    # return random value from scripts.Effect enumeration
    return random.choice(list(Effect))