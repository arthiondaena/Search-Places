import config
import logging
import json

from utils import get_address_GPS_coord, get_places, get_place_reviews, infer_client
from openai import OpenAI
from dotenv import dotenv_values

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

env = dotenv_values(".env")
client = OpenAI(base_url=config.BASE_URL, api_key=env["LLM_API_KEY"])

user_prompt = "Cafes with live music and Indian cuisine in Hyderabad"

extracted_location = infer_client(client, config.EXTRACT_LOC_TEMPLATE.format(user_prompt=user_prompt), config.LLM_MODEL)
logger.info(f"Extracted Location: {extracted_location}")

location_coordinates = get_address_GPS_coord(extracted_location, env["GOOGLE_MAPS_API_KEY"])
logger.info(f"Location Coordinates: {location_coordinates}")

places_output = get_places(user_prompt, env["SERPAPI_API_KEY"], location_coordinates, 1)
# logger.info(f"Places: {places_output}")

with open("outputs/places.json", "w") as f:
    json.dump(places_output, f, indent=4)

places = []

for page in places_output:
    places.extend(page["local_results"])

# Only taking the first 10 places into account
places = places[:10]

for i, place in enumerate(places):
    place_id = place["place_id"]
    reviews_output = get_place_reviews(place_id, env["SERPAPI_API_KEY"], 2)
    # logger.info(f"Reviews: {reviews_output}")
    try:
        with open(f"outputs/reviews/{place["title"]}.json", "w") as f:
            json.dump(reviews_output, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving reviews for {place['title']}: {e}")

    places[i]["reviews_content"] = []

    for page in reviews_output:
        reviews = page["reviews"]
        for review in reviews:
            review_dict = {"iso_date": review["iso_date"], "rating": review["rating"], "text": review["snippet"]}
            places[i]["reviews_content"].append(review_dict)

with open("outputs/places_with_reviews.json", "w", encoding="utf8") as f:
    json.dump(places, f, indent=4)

markdown_output = infer_client(client, config.FILTER_PLACES_TEMPLATE.format(user_prompt=user_prompt, places=places), config.LLM_MODEL)

with open("outputs/filtered_places.md", "w", encoding="utf8") as f:
    f.write(markdown_output)