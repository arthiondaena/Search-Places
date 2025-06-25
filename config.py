BASE_URL = "https://openrouter.ai/api/v1"
# LLM_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
LLM_MODEL = "google/gemini-2.0-flash-exp:free"

REQUIRED_COLUMNS_PLACES = ["title", "place_id", "gps_coordinates", "rating", "reviews", "price", "types", "type_id",
                           "type_ids", "address", "open_state", "hours", "operating_hours", "phone", "website",
                           "description", "extensions", "service_options"]

EXTRACT_LOC_TEMPLATE = """
Task:
Extract the location from the following user prompt. The location can be a city, state, country, neighborhood, or landmark mentioned in the prompt. If no location is present, return "None".

Input:
{user_prompt}

Output:
Location: <extracted_location>
"""

FILTER_PLACES_TEMPLATE = """
You are a helpful assistant that takes a user's prompt for a place (like a cafe or restaurant) and a list of place metadata, and returns a well-formatted Markdown list of the **top 5–10 most relevant places** that match the user's needs.

## Instructions:

- Read the user's prompt carefully.
- Understand the **intent**, such as:
  - Cuisine (e.g., Indian, Sushi)
  - Atmosphere (e.g., live music, romantic, cozy)
  - Recency (e.g., recently opened)
  - Type of place (e.g., cafe, bakery)
  - Location
- Use the place metadata (e.g., ratings, reviews, type, offerings, highlights, description, crowd, etc.) to evaluate matches.
- Use both structured data and unstructured `reviews_content` to enrich your understanding.
- The output should be a Markdown file listing the **Top 5–10 matching places**, sorted by relevance (not just rating).
- The markdown should be stylized so that it looks professional and informative.
- Each place must include:
  - **Title**
  - **Rating** and number of reviews
  - **Price level**
  - **Description** (shortened to 1–2 lines)
  - **Why this place fits the prompt** (short justification)
  - **Include 1–2 user reviews per place that specifically support why it was selected.**
    - Focus on sentiment matching user query (e.g., “great live music”, “amazing sushi”, “cozy vibe”)
    - Ignore overly generic or repeated statements
  - **Address**
  - **Opening hours**
  - **Phone number**
  - **Extensions that are suitable when taken user prompt into account**
  - **Link to Website or Google Maps**

---

## User prompt:
{user_prompt}

## Places Data:
```json
{places}
```
"""