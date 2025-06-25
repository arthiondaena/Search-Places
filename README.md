# Search-Places

## Setup Instructions

1. **Clone the repository**
   ```sh
   git clone <repository-url>
   cd Search-Places
   ```

2. **Create and activate a virtual environment**
   ```sh
   python -m venv venv
   # On Windows
   venv\Scripts\activate
   # On Unix or MacOS
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```sh
   pip install -r requirements.txt
   ```

4. **Configure environment variables**

   Create a `.env` file in the project root with the following template:

   ```
   # .env template
   HASDATA_API_KEY=hasdata_api_key
   SCRAPINGDOG_API_KEY=scrapingdog_api_key
   GOOGLE_MAPS_API_KEY=your_google_maps_api_key
   LLM_API_KEY=your_llm_api_key
   ```

   Replace the placeholder values with your actual API keys.

## Running the Application

To run the main script:

```sh
python main.py
```

To run the streamlit app:

```sh
streamlit run app.py
```

Make sure your virtual environment is activated and the `.env` file is present in the project root.
