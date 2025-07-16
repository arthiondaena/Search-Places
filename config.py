BASE_URL = "https://openrouter.ai/api/v1"
BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
# LLM_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
# LLM_MODEL = "google/gemini-2.0-flash-exp:free"
LLM_MODEL = "deepseek/deepseek-r1-0528:free"
LLM_MODEL = "deepseek/deepseek-chat-v3-0324:free"
LLM_MODEL = "gemini-2.5-flash-lite-preview-06-17"

NUM_PLACES = 15
NUM_REVIEWS = 40

REQUIRED_COLUMNS_PLACES = ["title", "place_id", "gps_coordinates", "rating", "reviews", "price", "types", "type_id",
                           "type_ids", "address", "open_state", "hours", "operating_hours", "phone", "website",
                           "description", "extensions", "service_options"]

MERGE_COLUMNS_SCRAPINGDOG_PLACES = ["type", "type_ids", "service_options", "extensions"]

REQUIRED_COLUMNS_INFER = ["title", "rating", "reviews", "price", "type", "types", "type_ids", "address", "open_state", "hours", "phone", "website", "image", "thumbnail", "description", "extensions", "google_maps_url", "show_image", "service_options", "extensions", "reviews_content"]

EXTRACT_LOC_TEMPLATE = """
Task:
Extract the location from the following user prompt. The location can be a city, state, country, neighborhood, or landmark mentioned in the prompt. If no location is present, return "None".
Don't mention anything other than the location itself, and do not include any additional text or explanation.

Input:
{user_prompt}

Output:
extracted location
"""

FILTER_PLACES_README_TEMPLATE = """
You are a helpful assistant that takes a user's natural language prompt about a type of place they’re looking for (e.g., cafe, restaurant, bakery) and a list of metadata-rich place entries, then returns a **well-structured, modern Markdown file** suitable for display on a webpage or blog.

---

## Output Requirements

Generate a **Markdown document listing the top 5–10 most relevant places**, selected based on the user’s prompt and the provided structured + unstructured data.

### Each place entry must include the following fields in a consistent, clean format:

#### **Title**  
- **Rating**: (e.g., 4.6/5 from 230 reviews)  
- **Price Level**: (e.g., $, $$, $$$)  
- **Short Description**: A brief 1–2 line summary  
- **Why this place fits the prompt**: A concise explanation tied directly to user query intent (e.g., cuisine, vibe, unique offering)  
- **User Reviews**: Include 1–2 short quotes that directly support the fit (e.g., “incredible Indian fusion snacks”, “great live music on weekends”)  
- **Address**  
- **Opening Hours**  
- **Phone Number**  
- **Website or Google Maps Link**  
- **Extensions** (optional): Mention any additional features that align with the user prompt (e.g., "rooftop seating", "vegan options", "pet-friendly")

---

## Relevance Guidelines

Evaluate each place carefully by analyzing both the **user's intent** and the **place metadata**.

### Understand intent from the user prompt:
- Type of place (e.g., cafe, fine-dining, street food)
- Cuisine (e.g., Indian, Japanese, fusion)
- Ambience or vibe (e.g., cozy, live music, romantic)
- Recency (e.g., “recently opened”, “new”)
- Location (city, area, or neighborhood)

### Use structured fields:
- Type, tags, cuisine, highlights, description, pricing, ratings

### Use unstructured data:
- **reviews_content** to extract relevant sentiments (e.g., mentions of “great atmosphere”, “authentic food”, “quiet for work”)

Sort the final list by **relevance to user prompt**, not just rating or popularity.

#### Image Handling

Each place entry includes a `"show_image"` field in the dataset with a direct image URL. Use this image prominently in the layout.

---

## Input Format

### User Prompt:
```plaintext
{user_prompt}
```

### Places Data:
```json
{places}
```

---

## Output Format

Return a single **well-formatted Markdown document**. Do **not** include explanation, preamble, or JSON. Just return the Markdown content.

The formatting should follow clean, semantic structure, with:
- Bold labels
- Clear sections
- No emojis or decorative characters
- Space between entries for easy reading
- Consistent heading levels (e.g., `##` for each place)
"""

FILTER_PLACES_HTML_TEMPLATE ="""
You are a helpful assistant that takes a user’s natural language prompt describing the type of place they’re looking for (e.g., cafe, sushi bar, bakery), along with a structured JSON dataset containing multiple place entries. Your task is to generate a **modern, clean HTML page** listing the **top 5–10 most relevant places** based on the prompt.

---

## 📄 Output Requirements

Return a complete HTML document styled for **modern web design**, optimized for embedding in a webpage or static site.

The output should be:
- Mobile-responsive
- Cleanly structured using semantic HTML
- Lightly styled using inline `<style>` or embedded CSS (you may use minimal classes and utility styles)
- Well-spaced and readable, using modern typography and layout

---

## 🧠 Matching Criteria

Analyze the user prompt for:
- **Place type** (e.g., cafe, rooftop bar, bakery)
- **Cuisine** (e.g., Indian, Sushi, Fusion)
- **Atmosphere** (e.g., romantic, live music, cozy, work-friendly)
- **Recency** (e.g., "new", "recently opened", "trending")
- **Location** (e.g., city, neighborhood)

From the `places` dataset:
- Use both **structured fields** and unstructured `reviews_content` to evaluate matches
- Use metadata such as `type`, `description`, `rating`, `price_level`, `highlights`, and `tags`
- Prefer **relevance to the prompt** over just highest rating

---

## 🖼️ Image Handling

Each place entry includes a `"show_image"` field in the dataset with a direct image URL. Use this image prominently in the layout (e.g., hero/banner style at the top of each card or section).
Add referrerpolicy="no-referrer" property for imgsrc tags.

---

## 🔖 Per Place Entry Structure

Each of the top 5–10 places should be rendered as a modern card or section with the following structure:

- **Image** (from `show_image`)
- **Name / Title**
- **Rating** (e.g., 4.6/5 from 180 reviews)
- **Price Level** (e.g., $, $$)
- **Short Description** (1–2 line summary)
- **Why this place fits the prompt** (short justification)
- **User Reviews** (1–2 quotes supporting the match)
- **Address**
- **Opening Hours**
- **Phone Number**
- **Website or Google Maps Link**
- **Extensions** (e.g., pet-friendly, rooftop seating, Wi-Fi, etc.)

Ensure the visual hierarchy is clear (headings, spacing, font weights), and sections are separated with cards or containers.

---

## 📥 Input

### User Prompt:
```plaintext
{user_prompt}
```

### Places Data:
```json
{places}
```

"""

FILTER_PLACES_JSON_TEMPLATE = """
You are a helpful assistant that takes a user's natural language prompt describing the type of place they are looking for (e.g., restaurant, cafe, bakery, hotel, resort, guesthouse, sightseeing spot, landmark, tourist attraction, adventure spot) along with a list of metadata-rich place entries. Your task is to analyze the prompt carefully and return a **JSON list of the top 5–10 most relevant places**, structured according to the specified format.

---

## ✅ Output Requirements

Return a **JSON array** of the most relevant places that best match the user’s query.
- Include **at least 5 and at most 7 places** if the total number of places is more than 5.
- If there are 5 or fewer places in total, return all of them.

---

## 🧭 Relevance Guidelines

Carefully analyze the user's intent, considering:

- **Type of place** (e.g., cafe, bakery, rooftop restaurant, boutique hotel, heritage guesthouse, adventure park, landmark, viewpoint)
- **Cuisine or food focus** (for dining places, e.g., local cuisine, vegan, continental, seafood)
- **Ambience or vibe** (e.g., romantic, family-friendly, luxury, budget-friendly, nature-focused, cozy, Instagram-worthy)
- **Recency or trends** (e.g., "newly opened", "currently popular", "trending")
- **Location** (city, neighborhood, nearby landmarks, general region)

Evaluate each place using:

### Structured Data
- Type, tags, cuisine (if applicable), highlights, price level, ratings, description, reviews count, features, extensions

### Unstructured Data
- **reviews_content**: Extract relevant sentiments, keywords, or expressions that indicate suitability for the user's request (e.g., "great for sunrise views", "adventurous trails", "cozy rooms", "excellent breakfast buffet").

### Prioritize
- Alignment with the user query is more important than highest rating or popularity alone.

---

## 🖼️ Image Handling

Each place entry will include an `"Image URL"` field (sometimes from `show_image`). Make sure to include this in the final JSON output.

---

## 💡 Input Format

### User Prompt
<user_prompt>
{user_prompt}
</user_prompt>

### Places Data
<places_data>
{places}
</places_data>
"""

CONVERT_PROMPT_TO_PARAMS = """
Today's date: {date}
Given a user prompt, extract the following parameters to be used for searching places:
If the check in and check out dates are not provided, use the tomorrow's date as the check-in date and the day after tomorrow as the check-out date.

<user_prompt>
{user_prompt}
</user_prompt>
"""