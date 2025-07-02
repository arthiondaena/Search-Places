import requests
import math
import urllib.parse
import config
import re

from datetime import datetime
from openai import OpenAI
from typing import Literal

def hasdata_maps_api(
        engine: Literal["search", "reviews"],
        params: dict,
    ) -> dict:
    """Fetch data from HasData Maps API."""
    assert "api_key" in params.keys(), "API key is required in params"

    api_url = "https://api.hasdata.com/scrape/google-maps"
    headers = {
        "x-api-key": params.pop('api_key'),
        "Content-Type": "application/json"
    }

    url_params = urllib.parse.urlencode(params)

    url = api_url + "/" + engine + "?" + url_params
    response = requests.get(url, headers=headers)
    return response.json()

def scrapingdog_maps_api(
        engine: Literal["search", "places", "reviews"],
        params: dict,
    ) -> dict:
    """Fetch data from ScrapingDog Maps API."""
    assert "api_key" in params.keys(), "API key is required in params"
    api_url = "http://api.scrapingdog.com/google_maps"

    url_params = urllib.parse.urlencode(params)

    if engine == "search":
        url = api_url + "?" + url_params
    else:
        url = api_url + "/" + engine + "?" + url_params

    response = requests.get(url)
    return response.json()

def get_geocode_data(address, api_key) -> dict:
    """Get geocode data for an address using Google Maps Geocoding API.

    Args:
        address: Address for which geocode is needed.
        api_key: API key for Google Maps Geocoding API.

    Returns:
        Dictionary containing geocode of the address.
    """
    params = {
        "address": address,
        "key": api_key
    }

    try:
        response = requests.get("https://maps.googleapis.com/maps/api/geocode/json", params=params)
        response.raise_for_status()  # Raise an exception for HTTP errors
        data = response.json()
        return data['results']
    except requests.exceptions.RequestException as e:
        return f"An error occurred: {e}"
    except KeyError:
        return "Unable to parse response data."

def bounds_zoom_level(bounds, map_width_px=800, map_height_px=600, zoom_max=21):
    """
    Given bounds and map dimensions, compute the max zoom level fitting both lat & lng.

    bounds: dict with 'northeast' and 'southwest', each having 'lat' & 'lng'
    """

    def lat_rad(lat):
        """Convert latitude to Mercator radian."""
        sin = math.sin(math.radians(lat))
        rad_x2 = math.log((1 + sin) / (1 - sin)) / 2
        return max(min(rad_x2, math.pi), -math.pi) / 2

    def zoom(map_px, world_px, fraction):
        """Calculate the zoom level for a given pixel/map/world ratio."""
        return math.floor(math.log(map_px / world_px / fraction) / math.log(2))

    ne = bounds['northeast']
    sw = bounds['southwest']
    WORLD_DIM = {'height': 256, 'width': 256}

    lat_fraction = (lat_rad(ne['lat']) - lat_rad(sw['lat'])) / math.pi
    lng_diff = ne['lng'] - sw['lng']
    if lng_diff < 0:
        lng_diff += 360
    lng_fraction = lng_diff / 360

    lat_zoom = zoom(map_height_px, WORLD_DIM['height'], lat_fraction)
    lng_zoom = zoom(map_width_px, WORLD_DIM['width'], lng_fraction)

    return min(lat_zoom, lng_zoom, zoom_max)

def get_address_GPS_coord(address, api_key):
    """Get GPS coordinates of an address using Google Maps Geocoding API.

    Args:
        Args:
        address: Address for which GPS coord and zoom level are needed.
        api_key: API key for Google Maps Geocoding API.

    Returns:
        Dictionary containing geocode and zoom level of the address.
    """
    data = get_geocode_data(address, api_key)[0]
    GPS = data["geometry"]["location"]
    GPS['zoom'] = bounds_zoom_level(data["geometry"]["bounds"])
    return GPS

def get_places(query: str, api_key: str, gps: dict, pages: int, service: Literal["hasdata", "scrapingdog"] = "hasdata"):
    """Get places based on a query. Every page contains 20 places.

    Args:
        query: The query to search for places.
        api_key: API key of SerpAPI.
        gps: A dict containing lat, lng, and zoom level of the location to search for places in.
        pages: Number of pages to fetch. It's better to limit the pages to 6 or less.
            More than that, the result might be duplicated or irrelevant.
        service: The service to use for fetching places. Can be either 'hasdata' or 'scrapingdog'.

    Returns:
        A list of dicts containing the raw output from SerpAPI.
    """
    if service not in ["hasdata", "scrapingdog"]:
        raise ValueError("Service must be either 'hasdata' or 'scrapingdog'.")

    if service == "hasdata":
        params = {
            "api_key": api_key,
            "engine": "google_maps",
            "q": query,
            "ll": f"@{gps['lat']},{gps['lng']},{gps['zoom']}z",
            "start": "0"
        }
    elif service == "scrapingdog":
        params = {
            "api_key": api_key,
            "type": "search",
            "query": query,
            "ll": f"@{gps['lat']},{gps['lng']},{gps['zoom']}z",
            "page": "0"
        }
    else:
        params = {}

    final_result = []

    for _ in range(pages):
        # Fetch places from SerpAPI.
        if service == "hasdata":
            results = hasdata_maps_api("search", params.copy())
        elif service == "scrapingdog":
            results = scrapingdog_maps_api("search", params.copy())
            # TODO : remove next line for production use.
            results["search_results"] = results["search_results"][:5]
            for i, place in enumerate(results["search_results"]):
                place_details = scrapingdog_maps_api("places", {"data_id": place["data_id"], "api_key": api_key})
                place_details = place_details['place_results']
                for col in config.MERGE_COLUMNS_SCRAPINGDOG_PLACES:
                    results["search_results"][i][col] = place_details.get(col, None)
                results["search_results"][i]["show_image"] = results["search_results"][i]["image"]
        else:
            results = {}

        # Append the results to the final result list.
        final_result.append(results)

        # Update the page offset.
        if service == "hasdata":
            params['start'] = str(int(params['start']) + 20)
        elif service == "scrapingdog":
            params['page'] = str(int(params['page']) + 20)

    return final_result

def get_place_reviews(data_id: str, api_key: str, pages: int, start_date: datetime = None, service: Literal["hasdata", "scrapingdog"] = "scrapingdog") -> list:
    """Get reviews of a place.

    The first page contains 8 reviews, and from the second page, 20 reviews are returned.
    The number of reviews is truncated based on pages or start_date, whichever comes first.
    The reviews are sorted based on their date.

    Args:
        data_id: Data IDs uniquely identify a place in the Google Places database.
        api_key: API key of SerpAPI.
        pages: Number of pages to fetch.
        start_date: Start date of reviews.
        service: The service to use for fetching reviews. Can be either 'hasdata' or 'scrapingdog'.

    Returns:
        A list of dicts containing the raw output from SerpAPI.
    """
    if service not in ["hasdata", "scrapingdog"]:
        raise ValueError("Service must be either 'hasdata' or 'scrapingdog'.")

    if service == "hasdata":
        params = {
            "dataId": data_id,
            "api_key": api_key,
            "sortBy": "newestFirst"
        }
    elif service == "scrapingdog":
        params = {
            "data_id": data_id,
            "api_key": api_key,
            "sort_by": "newestFirst",
        }
    else:
        params = {}
    final_result = []

    for _ in range(pages):
        # Fetch reviews from respective service.
        if service == "hasdata":
            results = hasdata_maps_api("reviews", params.copy())
        elif service == "scrapingdog":
            results = scrapingdog_maps_api("reviews", params.copy())
        else:
            results = {}

        # Check if the date of the first review is before the start date.
        if start_date and datetime.fromisoformat(results["reviews"][0]["iso_date"]) < start_date:
            break

        # Append the results to the final result list.
        final_result.append(results)

        # Update the next page token and number of reviews per page.
        if service == "scrapingdog":
            params['next_page_token'] = results["pagination"]["next_page_token"]
        elif service == "hasdata":
            params['nextPageToken'] = results["pagination"]["nextPageToken"]

        params['results'] = "20"

    return final_result

def infer_client(client: OpenAI, prompt: str, model: str):
    MAX_TRIES = 3
    for _ in range(MAX_TRIES):
        try:
            output = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                timeout=60,
            )
            return output.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error inferring client: {e}")
            continue
    raise Exception("Failed to infer client after multiple attempts.")

def extract_code_blocks(text):
    pattern = r"```(?:\w+)?\n(.*?)\n```"
    matches = re.findall(pattern, text, re.DOTALL)
    return matches

def create_place_html(place):
    reviews_html = ''.join(
        f'<div class="review">"{review["review"]}"</div>' for review in place["User Reviews"]
    )

    return f"""
    <div class="card">
        <div class="card-hero">
            <img src="{place['Image URL']}" alt="{place['name']}" referrerpolicy="no-referrer">
        </div>
        <div class="card-content">
            <div class="card-header">
                <h2 class="place-title">{place['name']}</h2>
                <div class="rating">
                    <span class="rating-value">{place['rating']}</span>
                    <span class="reviews">({place["reviews"]} reviews)</span>
                </div>
            </div>
            <div class="price-level">{place['price Level']}</div>
            <div class="details">
                <p class="description">{place['description']}</p>
                <div class="match-reason">
                    <strong>Why this fits:</strong> {place['Why this place fits the prompt']}
                </div>
                <div class="reviews-section">
                    <h3>Recent Customer Feedback:</h3>
                    {reviews_html}
                </div>
                <div class="contact-grid">
                    <div class="info-group">
                        <h4>Address</h4>
                        <p>{place['Address']}</p>
                    </div>
                    <div class="info-group">
                        <h4>Opening Hours</h4>
                        <p>{place['Opening Hours']}</p>
                    </div>
                    <div class="info-group">
                        <h4>Phone</h4>
                        <p>{place['Phone Number']}</p>
                    </div>
                </div>
                <a href="{place['Website']}" class="btn" target="_blank">Visit Website</a>
                <a href="{place['Google Maps URL']}" class="btn" target="_blank">View on Google Maps</a>
            </div>
        </div>
    </div>
    """

def create_places_html(places: list, template_html: str) -> str:
    """Create HTML for a list of places."""
    place_cards = ''.join(create_place_html(place) for place in places)
    return template_html.replace('<!--PLACEHOLDER-->', place_cards)


if __name__ == "__main__":
    from dotenv import dotenv_values
    import json

    env = dotenv_values(".env")
    # results = get_places("Cafes in Hyderabad", config["SERPAPI_API_KEY"], 2)
    # with open("outputs/places.json", "w") as f:
    #     json.dump(results, f, indent=4)
    # print(get_geocode_data("Hyderabad", config["GOOGLE_MAPS_API_KEY"]))
    # print(get_address_GPS_coord("Malkajgiri", config["GOOGLE_MAPS_API_KEY"]))
    # results = get_place_reviews("0x3bcb972ac27e4959:0xa3d14c260e61ddb9", config["SCRAPINGDOG_API_KEY"], 2, service="scrapingdog")
    # results = get_place_reviews("0x3bcb972ac27e4959:0xa3d14c260e61ddb9", config["HASDATA_API_KEY"], 2, service="hasdata")
    # results = get_places("Cafes in Hyderabad", env["SCRAPINGDOG_API_KEY"], {"lat": 17.406498, "lng": 78.47724389999999, "zoom": 11}, 1, service="scrapingdog")
    # results = get_places("Cafes in Hyderabad", config["HASDATA_API_KEY"], {"lat": 17.406498, "lng": 78.47724389999999, "zoom": 11}, 2, service="hasdata")
    # print(results)
    # results = scrapingdog_maps_api("places", {"data_id": "0x3bcb972ac27e4959:0xa3d14c260e61ddb9", "api_key": config["SCRAPINGDOG_API_KEY"]})
    # print(results)
    with open("template.html", "r") as f:
        template_html = f.read()

    import json

    with open("outputs/2025-06-28_18-40-21/places_with_reviews.json", "r", encoding="utf8") as f:
        places = json.load(f)

    html_output = create_places_html(places, template_html)
    with open("outputs/2025-06-28_18-40-21/places.html", "w", encoding="utf8") as f:
        f.write(html_output)