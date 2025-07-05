import config
import functools
import logging
import json
import os
import boto3

from utils import get_address_GPS_coord, get_places, get_place_reviews, infer_client, extract_code_blocks, create_places_html
from openai import OpenAI
from dotenv import dotenv_values, load_dotenv
from typing import Literal

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

env = dotenv_values(".env")

ENVIRON = env.get("ENVIRON", "local")
s3_bucket = "search-places-storage"
s3_client = boto3.client("s3")

def upload_to_s3(file_content, s3_key, content_type="application/json"):
    if isinstance(file_content, str):
        file_content = file_content.encode("utf-8")
    s3_client.put_object(Bucket=s3_bucket, Key=s3_key, Body=file_content, ContentType=content_type)
    logger.info(f"Uploaded to s3://{s3_bucket}/{s3_key}")

def setup_logging(output_folder=None):
    """Setup logging to both terminal and file (local or S3)."""
    logger = logging.getLogger()
    logger.handlers.clear()
    logger.setLevel(logging.INFO)

    # Console handler (plain logs)
    console_handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (write to file or S3)
    if output_folder is not None:
        log_filename = f"{output_folder}/run.log"
        if ENVIRON == "prod":
            from io import StringIO
            log_buffer = StringIO()
            file_handler = logging.StreamHandler(log_buffer)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            logger._s3_log_buffer = log_buffer
            logger._s3_log_key = log_filename
        else:
            os.makedirs(output_folder, exist_ok=True)
            file_handler = logging.FileHandler(log_filename, encoding="utf8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

def flush_s3_log():
    """Flush the in-memory log buffer to S3 if in prod."""
    logger = logging.getLogger()
    if hasattr(logger, "_s3_log_buffer"):
        log_content = logger._s3_log_buffer.getvalue()
        upload_to_s3(log_content, logger._s3_log_key, content_type="text/plain")
        logger.removeHandler(logger.handlers[-1])
        del logger._s3_log_buffer
        del logger._s3_log_key

def log_function(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger.info(f"Entering {func.__name__}")
        result = func(*args, **kwargs)
        logger.info(f"Exiting {func.__name__}")
        return result
    return wrapper

@log_function
def fetch_places(user_prompt: str, client: OpenAI, service: Literal["scrapingdog", "hasdata"] = "scrapingdog", output_folder: str = None):
    logger.info(f"fetch_places called with user_prompt={user_prompt}, service={service}, output_folder={output_folder}")
    extracted_location = infer_client(client, config.EXTRACT_LOC_TEMPLATE.format(user_prompt=user_prompt),
                                      config.LLM_MODEL)
    logger.info(f"Extracted Location: {extracted_location}")

    location_coordinates = get_address_GPS_coord(extracted_location, env["GOOGLE_MAPS_API_KEY"])
    logger.info(f"Location Coordinates: {location_coordinates}")

    api_key = env["SCRAPINGDOG_API_KEY"] if service == "scrapingdog" else env["HASDATA_API_KEY"]
    logger.info(f"Using API key for service {service}")
    places_output = get_places(user_prompt, api_key, location_coordinates, pages=1, service=service)
    logger.info(f"Fetched places_output: {len(places_output)} pages")

    if output_folder is not None:
        logger.info(f"Saving places_output to {'S3' if ENVIRON == 'prod' else 'local'} at {output_folder}/places.json")
        if ENVIRON == "prod":
            s3_key = f"{output_folder}/places.json"
            upload_to_s3(json.dumps(places_output, indent=4), s3_key)
        else:
            os.makedirs(output_folder, exist_ok=True)
            with open(f"{output_folder}/places.json", "w", encoding="utf8") as f:
                json.dump(places_output, f, indent=4)
    places = []

    for page in places_output:
        logger.debug(f"Processing page: {page}")
        if service == "hasdata":
            places.extend(page["localResults"])
        else:
            places.extend(page["search_results"])

    logger.info(f"Returning {len(places)} places")
    return places

def _fetch_and_save_reviews(args):
    i, place, output_folder, env = args
    logger.info(f"Fetching reviews for place index={i}, title={place.get('title')}")
    dataId = place.get("dataId", place.get("data_id", None))
    if not dataId:
        logger.warning(f"No dataId found for place: {place}")
    reviews_output = get_place_reviews(dataId, env["SCRAPINGDOG_API_KEY"], pages=2, service="scrapingdog")
    logger.info(f"Fetched {sum(len(page['reviews_results']) for page in reviews_output)} reviews for {place.get('title')}")
    try:
        if output_folder is not None:
            filename = "".join(
                c for c in place["title"].replace(" ", "_") if c not in r"\/:*?<>|") + ".json"
            logger.info(f"Saving reviews for {place.get('title')} to {'S3' if ENVIRON == 'prod' else 'local'} at {output_folder}/reviews/{filename}")
            if ENVIRON == "prod":
                s3_key = f"{output_folder}/reviews/{filename}"
                upload_to_s3(json.dumps(reviews_output, indent=4), s3_key)
            else:
                os.makedirs(f"{output_folder}/reviews", exist_ok=True)
                with open(f"{output_folder}/reviews/{filename}", "w", encoding="utf8") as f:
                    json.dump(reviews_output, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving reviews for {place['title']}: {e}")

    reviews_content = []
    for page in reviews_output:
        reviews = page["reviews_results"]
        for review in reviews:
            review_dict = {"iso_date": review["iso_date"], "rating": review["rating"],
                           "text": review.get("snippet", "")}
            reviews_content.append(review_dict)
    logger.info(f"Returning {len(reviews_content)} reviews_content for place index={i}")
    return (i, reviews_content)

@log_function
def fetch_places_reviews(places, output_folder: str = None):
    logger.info(f"fetch_places_reviews called for {len(places)} places, output_folder={output_folder}")
    args_list = [(i, place, output_folder, env) for i, place in enumerate(places)]

    logger.info("Starting Parallel fetching")
    logger.warning("Failed Parallel fetching, falling back to sequential fetching")
    results = []
    for arg in args_list:
        logger.debug(f"Fetching reviews for place index={arg[0]}")
        results.append(_fetch_and_save_reviews(arg))
    logger.info("Completed Sequential fetching")

    # Update places with reviews_content
    for i, reviews_content in results:
        logger.debug(f"Attaching {len(reviews_content)} reviews to place index={i}")
        places[i]["reviews_content"] = reviews_content

    if output_folder is not None:
        logger.info(f"Saving places_with_reviews to {'S3' if ENVIRON == 'prod' else 'local'} at {output_folder}/places_with_reviews.json")
        if ENVIRON == "prod":
            s3_key = f"{output_folder}/places_with_reviews.json"
            upload_to_s3(json.dumps(places, indent=4, ensure_ascii=False), s3_key)
        else:
            with open(f"{output_folder}/places_with_reviews.json", "w", encoding="utf8") as f:
                json.dump(places, f, indent=4, ensure_ascii=False)
    logger.info(f"Returning places with reviews, count={len(places)}")
    return places

@log_function
def filter_places(places: list, user_prompt: str, client: OpenAI, output_type: Literal["markdown", "html"] = "html", output_folder: str = None):
    logger.info(f"filter_places called with {len(places)} places, user_prompt={user_prompt}, output_type={output_type}, output_folder={output_folder}")
    template = config.FILTER_PLACES_JSON_TEMPLATE if output_type == "html" else config.FILTER_PLACES_README_TEMPLATE

    output = infer_client(client, template.format(user_prompt=user_prompt, places=places), config.LLM_MODEL)
    logger.info("LLM output received")

    # Extract code blocks from the output if present
    code_blocks = extract_code_blocks(output)
    if code_blocks:
        logger.info("Extracted code block from LLM output")
        output = code_blocks[0]
    else:
        logger.info("No code block found in LLM output")

    if output_type == "html":
        logger.info("Parsing LLM output as Python object for HTML rendering")
        output = eval(output)
        if output_folder is not None:
            logger.info(f"Saving filtered_places.json to {'S3' if ENVIRON == 'prod' else 'local'} at {output_folder}/filtered_places.json")
            if ENVIRON == "prod":
                s3_key = f"{output_folder}/filtered_places.json"
                upload_to_s3(json.dumps(output, indent=4, ensure_ascii=False), s3_key)
            else:
                with open(f"{output_folder}/filtered_places.json", "w", encoding="utf8") as f:
                    json.dump(output, f, indent=4, ensure_ascii=False)
        with open("template.html", "r", encoding="utf8") as f:
            template_html = f.read()
        logger.info("Creating HTML output from filtered places")
        output = create_places_html(output, template_html)

    if output_folder is not None:
        output_file = f"{output_folder}/filtered_places.md" if output_type == "markdown" else f"{output_folder}/filtered_places.html"
        content_type = "text/markdown" if output_type == "markdown" else "text/html"
        logger.info(f"Saving filtered places output to {'S3' if ENVIRON == 'prod' else 'local'} at {output_file}")
        if ENVIRON == "prod":
            upload_to_s3(output, output_file, content_type=content_type)
        else:
            with open(output_file, "w", encoding="utf8") as f:
                f.write(output)

    logger.info("Returning filtered places output")
    return output

@log_function
def main(user_prompt: str, save_output: str = None):
    logger.info(f"main called with user_prompt={user_prompt}, save_output={save_output}")
    if save_output:
        output_folder = save_output
    else:
        output_folder = None

    setup_logging(output_folder)

    client = OpenAI(base_url=config.BASE_URL, api_key=env["LLM_API_KEY"])

    if output_folder is not None and ENVIRON == "local":
        os.makedirs(output_folder, exist_ok=True)
        os.makedirs(f"{output_folder}/reviews", exist_ok=True)

    logger.info("Fetching places...")
    places = fetch_places(user_prompt, client, "scrapingdog", output_folder)

    # TODO: Only taking the first 10 places into account
    logger.info(f"Limiting places to first 2 for processing")
    places = places[:2]

    logger.info("Fetching reviews for places...")
    places = fetch_places_reviews(places, output_folder)

    logger.info("Filtering places using LLM...")
    output = filter_places(places, user_prompt, client, "html", output_folder)

    if ENVIRON == "prod" and output_folder is not None:
        logger.info("Flushing logs to S3")
        flush_s3_log()

    logger.info("main completed successfully")
    return output

def lambda_handler(event, context):
    setup_logging(context.aws_request_id)
    logger.info(f"lambda_handler called with event={event}, context={context}")
    # Generate a unique ID for this request
    request_id = str(context.aws_request_id)

    logger.info(f"Request ID: {request_id} - Received event: {json.dumps(event)}")
    try:
        user_prompt = event.get("user_prompt", "Cafes with live music and Indian cuisine in Hyderabad")
        output_type = event.get("output_type", "html")
        logger.info(f"Calling main with user_prompt={user_prompt}, output_type={output_type}, request_id={request_id}")

        output = main(user_prompt, request_id)

        logger.info("lambda_handler completed successfully")
        return {
            "statusCode": 200,
            "request_id": request_id,
            "body": output
        }
    except Exception as e:
        logger.error(f"Error in lambda_handler: {e}", exc_info=True)
        if ENVIRON == "prod":
            flush_s3_log()
        return {
            "statusCode": 500,
            "body": f"An error occurred. Reference ID: {request_id}. Please try again later.",
        }

if __name__ == "__main__":
    import uuid
    class context:
        aws_request_id = str(uuid.uuid4())
    logger.info("Starting script in __main__")
    lambda_handler({"user_prompt": "Cafes with live music and Indian cuisine in Hyderabad"}, context())
    # main("Cafes with live music and Indian cuisine in Hyderabad", save_output=True)
    # import json
    # with open("outputs/2025-06-28_22-56-33/places_with_reviews.json", "r", encoding="utf8") as f:
    #     places = json.load(f)
    #
    # markdown_output = filter_places(places, "Cafes with live music and Indian cuisine in Hyderabad", OpenAI(base_url=config.BASE_URL, api_key=env["LLM_API_KEY"]), "html", "outputs/2025-06-28_22-56-33")
    # main("cafe with Asian cuisine in hyderabad", save_output=True)
    # markdown_output = filter_places(places, "Cafes with live music and Indian cuisine in Hyderabad", OpenAI(base_url=config.BASE_URL, api_key=env["LLM_API_KEY"]), "html", "outputs/2025-06-28_22-56-33")
    # main("cafe with Asian cuisine in hyderabad", save_output=True)
