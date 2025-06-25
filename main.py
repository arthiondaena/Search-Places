import config
from datetime import datetime
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

def fetch_places(user_prompt: str, client: OpenAI, output_folder: str = None):
    """Fetches places based on the user prompt and saves the output to a specified folder."""
    extracted_location = infer_client(client, config.EXTRACT_LOC_TEMPLATE.format(user_prompt=user_prompt),
                                      config.LLM_MODEL)
    logger.info(f"Extracted Location: {extracted_location}")

    location_coordinates = get_address_GPS_coord(extracted_location, env["GOOGLE_MAPS_API_KEY"])
    logger.info(f"Location Coordinates: {location_coordinates}")

    places_output = get_places(user_prompt, env["HASDATA_API_KEY"], location_coordinates, pages=1, service="hasdata")

    if output_folder is not None:
        with open(output_folder + "/places.json", "w") as f:
            json.dump(places_output, f, indent=4)

    places = []

    # TODO: Handle pagination differently when using scrapingdog service for get_places.
    for page in places_output:
        places.extend(page["localResults"])

    return places

def fetch_places_reviews(places, output_folder: str = None):
    """Fetches reviews for each place and saves them to the specified output folder."""
    for i, place in enumerate(places):
        dataId = place["dataId"]
        reviews_output = get_place_reviews(dataId, env["SCRAPINGDOG_API_KEY"], pages=2, service="scrapingdog")
        try:
            if output_folder is not None:
                # Remove invalid characters and replace space with underscore from the title to create a valid filename.
                filename = output_folder + "/reviews/" + "".join(i for i in place["title"].replace(" ", "_") if i not in "\/:*?<>|") + ".json"
                with open(filename, "w") as f:
                    json.dump(reviews_output, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving reviews for {place['title']}: {e}")

        places[i]["reviews_content"] = []

        for page in reviews_output:
            reviews = page["reviews_results"]
            for review in reviews:
                review_dict = {"iso_date": review["iso_date"], "rating": review["rating"], "text": review.get("snippet", "")}
                places[i]["reviews_content"].append(review_dict)

    if output_folder is not None:
        with open(output_folder + "/places_with_reviews.json", "w", encoding="utf8") as f:
            json.dump(places, f, indent=4)

    return places

def filter_places(places: list, user_prompt: str, client: OpenAI, output_folder: str = None):
    """Filters places based on the user prompt using the LLM."""
    markdown_output = infer_client(client, config.FILTER_PLACES_TEMPLATE.format(user_prompt=user_prompt, places=places), config.LLM_MODEL)

    if output_folder is not None:
        with open(output_folder + "/filtered_places.md", "w", encoding="utf8") as f:
            f.write(markdown_output)

    return markdown_output

def main(user_prompt: str, save_output: bool = False):
    """Main function to execute the place review fetching and filtering process."""
    if save_output:
        output_folder = "outputs" + "/" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    else:
        output_folder = None

    client = OpenAI(base_url=config.BASE_URL, api_key=env["LLM_API_KEY"])

    if save_output:
        import os
        os.makedirs(output_folder, exist_ok=True)
        os.makedirs(output_folder + "/reviews", exist_ok=True)

    places = fetch_places(user_prompt, client, output_folder)

    # Only taking the first 10 places into account
    places = places[:10]

    places = fetch_places_reviews(places, output_folder)

    markdown_output = filter_places(places, user_prompt, client, output_folder)

    return markdown_output

if __name__ == "__main__":
    # main("Cafes with live music and Indian cuisine in Hyderabad", save_output=True)
    import json
    with open("outputs/2025-06-25_20-50-10/places_with_reviews.json", "r", encoding="utf8") as f:
        places = json.load(f)

    markdown_output = filter_places(places, "Cafes with live music and Indian cuisine in Hyderabad", OpenAI(base_url=config.BASE_URL, api_key=env["LLM_API_KEY"]), "outputs/2025-06-25_20-50-10")