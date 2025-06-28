import config

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from main import fetch_places, fetch_places_reviews, filter_places
from openai import OpenAI
from dotenv import dotenv_values
from datetime import datetime

app = FastAPI()


@app.get("/run")
def run(user_prompt: str):
    try:
        env = dotenv_values(".env")
        client = OpenAI(base_url=config.BASE_URL, api_key=env["LLM_API_KEY"])
        # TODO: Setup S3 bucket for output storage.
        def stream_generator():
            yield "data: Starting the process...\n\n"

            try:
                places = fetch_places(user_prompt, client, "scrapingdog")
                # TODO: Remove this limit in production
                places = places[:2]
                yield "data: Fetched places successfully.\n\n"
            except Exception as e:
                yield f"data: Error fetching places: {str(e)}\n\n"
                return

            try:
                places = fetch_places_reviews(places)
                yield "data: Fetched reviews for places successfully.\n\n"
            except Exception as e:
                yield f"data: Error fetching reviews: {str(e)}\n\n"
                return

            try:
                output = filter_places(places, user_prompt, client, "html")
                yield "data: Filtered places successfully.\n\n"
                yield f"data: {output}\n\n"
            except Exception as e:
                yield f"data: Error filtering places: {str(e)}\n\n"
                return

        return StreamingResponse(stream_generator(), media_type="text/event-stream")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error processing document: {str(e)}"
        )