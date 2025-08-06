import logging
from urllib import parse
import urllib.request
import json

from log.loggers.rotating_logger import get_rotating_logger

# Set up rotating logger with 10MB max size and 5 backup files
logger = get_rotating_logger(__name__)

# Response format:
#   <@Username>, <Name of Dish> - Ingredients: <comma separated ingredients>,
#   <youtube link>

url = "https://www.themealdb.com/api/json/v1/1/random.php"


def _request() -> dict:
    global url

    print(url)

    with urllib.request.urlopen(url) as response:
        j = json.loads(response.read())
        meal = j["meals"][0]  # strip unnecessary typing

    return meal


def _parse_ingredients(raw_response: dict) -> str:
    """
    Parse raw meal response dict, find the ingredients, and return
    a string of the ingredients separated by commas.
    """
    ingredients = ""
    print(type(raw_response))
    for key, value in raw_response.items():
        if "ingredient" not in key.lower():
            continue
        if len(value) == 0:
            continue
        ingredients = ingredients + value.lower() + ", "

    ingredients = ingredients.strip(", ")

    return ingredients


def get_meal() -> str:
    """
    Returns a string of the formatted recipe response.
    """
    raw = _request()
    name = raw["strMeal"]
    category = raw["strCategory"]
    area = raw["strArea"]
    youtube = raw["strYoutube"]
    ingredients = _parse_ingredients(raw)

    formatted_response = (
        f"{name} ({category}, {area}) - Ingredients: {ingredients}, {youtube}"
    )

    return formatted_response
