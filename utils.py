import requests
import math
from datetime import datetime
from serpapi import GoogleSearch
from openai import OpenAI

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

def get_places(query: str, api_key: str, gps: dict, pages: int):
    """Get places based on a query. Every page contains 20 places.

    Args:
        query: The query to search for places.
        api_key: API key of SerpAPI.
        gps: A dict containing lat, lng, and zoom level of the location to search for places in.
        pages: Number of pages to fetch. It's better to limit the pages to 6 or less.
            More than that, the result might be duplicated or irrelevant.

    Returns:
        A list of dicts containing the raw output from SerpAPI.
    """
    params = {
        "api_key": api_key,
        "engine": "google_maps",
        "type": "search",
        "google_domain": "google.com",
        "q": query,
        "ll": f"@{gps['lat']},{gps['lng']},{gps['zoom']}z",
        "hl": "en",
        "start": "0"
    }
    final_result = []

    for _ in range(pages):
        # Fetch places from SerpAPI.
        search = GoogleSearch(params)
        results = search.get_dict()

        # Append the results to the final result list.
        final_result.append(results)

        # Update the page offset.
        params['start'] = str(int(params['start']) + 20)

    return final_result

def get_place_reviews(place_id: str, api_key: str, pages: int, start_date: datetime = None):
    """Get reviews of a place.

    The first page contains 8 reviews, and from the second page, 20 reviews are returned.
    The number of reviews is truncated based on pages or start_date, whichever comes first.
    The reviews are sorted based on their date.

    Args:
        place_id: Place IDs uniquely identify a place in the Google Places database.
        api_key: API key of SerpAPI.
        pages: Number of pages to fetch.
        start_date: Start date of reviews.

    Returns:
        A list of dicts containing the raw output from SerpAPI.
    """
    params = {
        "engine": "google_maps_reviews",
        "hl": "en",
        "place_id": place_id,
        "api_key": api_key
    }
    final_result = []

    for _ in range(pages):
        # Fetch reviews from SerpAPI.
        search = GoogleSearch(params)
        results = search.get_dict()

        # Check if the date of the first review is before the start date.
        if start_date and datetime.fromisoformat(results["reviews"][0]["iso_date"]) < start_date:
            break

        # Append the results to the final result list.
        final_result.append(results)

        # Update the next page token and number of reviews per page.
        params['next_page_token'] = results["serpapi_pagination"]["next_page_token"]
        params['num'] = "20"

    return final_result

def infer_client(client: OpenAI, prompt: str, model: str):
    output = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    return output.choices[0].message.content.strip()

if __name__ == "__main__":
    from dotenv import dotenv_values
    import json

    config = dotenv_values(".env")
    # results = get_places("Cafes in Hyderabad", config["SERPAPI_API_KEY"], 2)
    # with open("outputs/places.json", "w") as f:
    #     json.dump(results, f, indent=4)
    # print(get_geocode_data("Hyderabad", config["GOOGLE_MAPS_API_KEY"]))
    print(get_address_GPS_coord("Malkajgiri", config["GOOGLE_MAPS_API_KEY"]))