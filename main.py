import config
from datetime import datetime
import logging
import json
import concurrent.futures
import os

from utils import get_address_GPS_coord, get_places, get_place_reviews, infer_client, extract_code_blocks, create_places_html
from openai import OpenAI
from dotenv import dotenv_values
from typing import Literal

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

env = dotenv_values(".env")

def fetch_places(user_prompt: str, client: OpenAI, service: Literal["scrapingdog", "hasdata"] = "scrapingdog", output_folder: str = None):
    """Fetches places based on the user prompt and saves the output to a specified folder."""
    extracted_location = infer_client(client, config.EXTRACT_LOC_TEMPLATE.format(user_prompt=user_prompt),
                                      config.LLM_MODEL)
    logger.info(f"Extracted Location: {extracted_location}")

    location_coordinates = get_address_GPS_coord(extracted_location, env["GOOGLE_MAPS_API_KEY"])
    logger.info(f"Location Coordinates: {location_coordinates}")

    api_key = env["SCRAPINGDOG_API_KEY"] if service == "scrapingdog" else env["HASDATA_API_KEY"]
    # places_output = get_places(user_prompt, env["HASDATA_API_KEY"], location_coordinates, pages=1, service="hasdata")
    places_output = get_places(user_prompt, api_key, location_coordinates, pages=1, service=service)

    if output_folder is not None:
        with open(output_folder + "/places.json", "w") as f:
            json.dump(places_output, f, indent=4)

    places = []

    for page in places_output:
        if service == "hasdata":
            places.extend(page["localResults"])
        else:
            places.extend(page["search_results"])

    return places

def _fetch_and_save_reviews(args):
    """Helper function for parallel fetching and saving of reviews."""
    i, place, output_folder, env = args
    # TODO: Handle this case more gracefully.
    dataId = place.get("dataId", place.get("data_id", None))
    from utils import get_place_reviews  # Import inside for multiprocessing compatibility
    import json
    import logging
    logger = logging.getLogger(__name__)
    reviews_output = get_place_reviews(dataId, env["SCRAPINGDOG_API_KEY"], pages=2, service="scrapingdog")
    try:
        if output_folder is not None:
            # Remove invalid characters and replace space with underscore from the title to create a valid filename.
            filename = output_folder + "/reviews/" + "".join(i for i in place["title"].replace(" ", "_") if i not in r"\/:*?<>|") + ".json"
            with open(filename, "w") as f:
                json.dump(reviews_output, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving reviews for {place['title']}: {e}")

    reviews_content = []
    for page in reviews_output:
        reviews = page["reviews_results"]
        for review in reviews:
            review_dict = {"iso_date": review["iso_date"], "rating": review["rating"], "text": review.get("snippet", "")}
            reviews_content.append(review_dict)
    return (i, reviews_content)

def fetch_places_reviews(places, output_folder: str = None):
    """Fetches reviews for each place and saves them to the specified output folder using multiprocessing."""
    args_list = [(i, place, output_folder, env) for i, place in enumerate(places)]

    # Use ProcessPoolExecutor for CPU-bound or IO-bound tasks
    with concurrent.futures.ProcessPoolExecutor() as executor:
        results = list(executor.map(_fetch_and_save_reviews, args_list))

    # Update places with reviews_content
    for i, reviews_content in results:
        places[i]["reviews_content"] = reviews_content

    if output_folder is not None:
        with open(output_folder + "/places_with_reviews.json", "w", encoding="utf8") as f:
            json.dump(places, f, indent=4)

    return places

def filter_places(places: list, user_prompt: str, client: OpenAI, output_type: Literal["markdown", "html"] = "html", output_folder: str = None):
    """Filters places based on the user prompt using the LLM."""
    template = config.FILTER_PLACES_JSON_TEMPLATE if output_type == "html" else config.FILTER_PLACES_README_TEMPLATE

    output = infer_client(client, template.format(user_prompt=user_prompt, places=places), config.LLM_MODEL)

    # Extract code blocks from the output if present
    output = extract_code_blocks(output)[0] if extract_code_blocks(output) else output

    if output_type == "html":
        # TODO: Handle the case where the output is not a valid JSON (retrying the LLM call might be necessary)
        output = eval(output)
        if output_folder is not None:
            with open(output_folder + "/filtered_places.json", "w", encoding="utf8") as f:
                json.dump(output, f, indent=4)
        with open("template.html", "r", encoding="utf8") as f:
            template_html = f.read()
        output = create_places_html(output, template_html)

    if output_folder is not None:
        output_file = output_folder + "/filtered_places.md" if output_type == "markdown" else output_folder + "/filtered_places.html"
        with open(output_file, "w", encoding="utf8") as f:
            f.write(output)

    return output

def main(user_prompt: str, save_output: bool = False):
    """Main function to execute the place review fetching and filtering process."""
    if save_output:
        output_folder = "outputs" + "/" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    else:
        output_folder = None

    client = OpenAI(base_url=config.BASE_URL, api_key=env["LLM_API_KEY"])

    if save_output:
        os.makedirs(output_folder, exist_ok=True)
        os.makedirs(output_folder + "/reviews", exist_ok=True)

    places = fetch_places(user_prompt, client, "hasdata", output_folder)

    # TODO: Only taking the first 10 places into account
    places = places[:5]

    places = fetch_places_reviews(places, output_folder)

    markdown_output = filter_places(places, user_prompt, client, "markdown", output_folder)

    return markdown_output

if __name__ == "__main__":
    # main("Cafes with live music and Indian cuisine in Hyderabad", save_output=True)
    import json
    with open("outputs/2025-06-28_22-56-33/places_with_reviews.json", "r", encoding="utf8") as f:
        places = json.load(f)

    markdown_output = filter_places(places, "Cafes with live music and Indian cuisine in Hyderabad", OpenAI(base_url=config.BASE_URL, api_key=env["LLM_API_KEY"]), "html", "outputs/2025-06-28_22-56-33")
    # main("cafe with Asian cuisine in hyderabad", save_output=True)
