# items_provider.py
from langchain_llm7 import ChatLLM7
from langchain_core.messages import HumanMessage
import random
import pollinations
from PIL import Image

import uuid
llm = ChatLLM7()
model = pollinations.Image()


def get_text():
    thing = random.choice(["гриба", "камня", "жидкости", "растения"])
    response = llm.invoke([HumanMessage(content=f"Дай ОДНО случайное короткое название на русском инопланетного {thing}, которое могло бы быть съедено. 1-2 слова.")])
    if thing == "гриба":
        return "Гриб: " + response.content
    elif thing == "камня":
        return "Камень: " + response.content
    elif thing == "жидкости":
        return "Жидкость: " + response.content
    elif thing == "растения":
        return "Растение: " + response.content
    else:
        return response.content

def get_image(name):
    response = llm.invoke([HumanMessage(content="Создай красочное краткое описание инопланетного предмета на английском языке: " + name)])
    prompt = response.content
    image = model(prompt)
    img_name = f"img+{uuid.uuid4()}.png"
    image.save(img_name)
    return img_name

def get_random_item():
    name = get_text()
    return {
            "name": name,
            "image": get_image(name),
            "cost": random.choice([50, 100, 150, 200])
        }
