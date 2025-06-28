import streamlit as st
from main import fetch_places, fetch_places_reviews, filter_places
from openai import OpenAI
import config
from dotenv import dotenv_values
from datetime import datetime
import os

st.set_page_config(page_title="Search Places", layout="centered")

st.title("Search Places with Reviews")
st.markdown("Enter your search prompt below (e.g., 'Cafes with live music and Indian cuisine in Hyderabad').")

user_prompt = st.text_input("Search Prompt", "")
output_type = st.radio("Output Type", ["markdown", "html"], index=1)

if "output_folder" not in st.session_state:
    st.session_state["output_folder"] = None

if st.button("Search") and user_prompt.strip():
    st.session_state["output_folder"] = "outputs/" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    os.makedirs(st.session_state["output_folder"], exist_ok=True)
    os.makedirs(st.session_state["output_folder"] + "/reviews", exist_ok=True)

    env = dotenv_values(".env")
    client = OpenAI(base_url=config.BASE_URL, api_key=env["LLM_API_KEY"])

    with st.status("Starting...", expanded=True) as status:
        status.write("Fetching places...")
        places = fetch_places(user_prompt, client, "scrapingdog", st.session_state["output_folder"])

        status.write("Fetching reviews for places...")
        # TODO: Remove this limit in production
        places = places[:5]
        places = fetch_places_reviews(places, st.session_state["output_folder"])

        status.write("Filtering places...")
        output = filter_places(places, user_prompt, client, output_type, st.session_state["output_folder"])

        status.update(label="Done! See results below.", state="complete", expanded=False)

    st.markdown("---")
    if output_type == "markdown":
        st.markdown(output)
    else:
        st.html(output)