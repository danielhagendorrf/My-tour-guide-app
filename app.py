import streamlit as st
import google.generativeai as genai
from gtts import gTTS
from io import BytesIO
from PIL import Image
from datetime import datetime
import requests
from streamlit_geolocation import streamlit_geolocation
from streamlit_back_camera_input import back_camera_input
from google.api_core.exceptions import ResourceExhausted

# -----------------------------------------
# 1. ARCHITECTURE & EXTENSIBILITY SETUP
# -----------------------------------------
USER_PREFERENCES = {
    "food": ["Charcuterie", "Artisan pastries", "Premium burgers", "Local culinary workshops"],
    "activities": ["Escape rooms", "Trivia and pub quizzes", "Theater performances", "Orienteering"]
}

# -----------------------------------------
# 2. HELPER FUNCTIONS
# -----------------------------------------
def generate_audio(text, lang_code):
    tts = gTTS(text=text, lang=lang_code, slow=False)
    fp = BytesIO()
    tts.write_to_fp(fp)
    fp.seek(0)
    return fp

def get_location_context():
    if st.session_state.get('lat') and st.session_state.get('lon'):
        return f"Current Location: {st.session_state.lat} Latitude, {st.session_state.lon} Longitude."
    return "Location unknown."

def clean_for_audio(text):
    return text.replace("*", "").replace("#", "").replace('"', "").replace("_", "")

def fetch_live_search_tavily(query, api_key):
    if not api_key:
        return "[Live Search Disabled: No Tavily API Key provided.]"
    
    url = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "basic",
        "include_answer": False,
        "max_results": 5
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        data = res.json()
        if "results" in data:
            snippets = [r.get("content", "") for r in data["results"]]
            return "\n- ".join(snippets)
    except Exception as e:
        return f"[Live Search Error: {e}]"
    return "No recent events or live data found on the web."

# -----------------------------------------
# 3. APP INITIALIZATION & SIDEBAR
# -----------------------------------------
st.set_page_config(page_title="Personal AI Guide", layout="wide")
st.title("🌍 My Personal AI Tour Guide")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "lat" not in st.session_state:
    st.session_state.lat = None
if "lon" not in st.session_state:
    st.session_state.lon = None
if "guide_text" not in st.session_state:
    st.session_state.guide_text = ""
if "guide_audio" not in st.session_state:
    st.session_state.guide_audio = None
if "camera_active" not in st.session_state:
    st.session_state.camera_active = False
if "last_image_id" not in st.session_state:
    st.session_state.last_image_id = None
if "pending_image" not in st.session_state:
    st.session_state.pending_image = None
if "raw_search_data" not in st.session_state:
    st.session_state.raw_search_data = ""

with st.sidebar:
    st.header("⚙ Setup")
    api_keys = st.secrets.get("GEMINI_API_KEYS", [])
    if not api_keys:
        manual_key = st.text_input("Enter Gemini API Key", type="password")
        if manual_key: api_keys = [manual_key]
            
    tavily_key = st.secrets.get("TAVILY_API_KEY", "")
    if not tavily_key:
        manual_tavily = st.text_input("Enter Tavily Search Key", type="password")
        if manual_tavily: tavily_key = manual_tavily
            
    if not api_keys:
        st.warning("Please enter your Gemini API Key to begin.")
        st.stop()
        
    st.subheader("🌐 Language / שפה")
    lang_choice = st.radio("Select your preferred language:", ["English", "Hebrew (עברית)"])

target_lang = "English" if lang_choice == "English" else "Hebrew"
tts_lang = "en" if lang_choice == "English" else "iw"

# -----------------------------------------
# 4. MAIN INTERFACE (TABS)
# -----------------------------------------
tab1, tab2, tab3 = st.tabs(["📸 Photo Guide", "🧭 Explore Nearby", "💬 Chat & Ask"])

# --- TAB 1: Photo & Audio Guide ---
with tab1:
    st.header("Scan a Landmark")
    
    if st.button("📷 Open / Close Camera"):
        st.session_state.camera_active = not st.session_state.camera_active
        st.session_state.pending_image = None
        st.rerun()
        
    image_source = None
    trigger_generation = False
    
    if st.session_state.pending_image:
        st.success("📸 Photo captured! Analyzing landmark...")
        image_source = st.session_state.pending_image
        trigger_generation = True
        
    elif st.session_state.camera_active:
        st.info("💡 **Tip:** Tap directly on the camera video feed to snap your photo.")
        camera_photo = back_camera_input()
        if camera_photo:
            if st.session_state.last_image_id != camera_photo.getvalue():
                st.session_state.last_image_id = camera_photo.getvalue()
                st.session_state.pending_image = camera_photo
                st.rerun()
    else:
        uploaded_file = st.file_uploader("Or upload from your camera roll", type=["jpg", "jpeg", "png"])
        if uploaded_file:
            image_source = uploaded_file
            if st.button("Generate Audio Guide"):
                trigger_generation = True

    if image_source and trigger_generation:
        image = Image.open(image_source)
        try:
            prompt = f"""
            {get_location_context()}
            Act as an expert, engaging tour guide. Identify the landmark or subject in this image. 
            Provide a 2-minute fascinating historical overview. End with one interesting fact.
            Write the entire response strictly in {target_lang}.
            """
            message_placeholder = st.empty()
            temp_guide_text = ""
            success = False
            
            for key in api_keys:
                try:
                    genai.configure(api_key=key)
                    model = genai.GenerativeModel('gemini-3.5-flash-lite')
                    response = model.generate_content([prompt, image], stream=True)
                    for chunk in response:
                        if chunk.text:
                            temp_guide_text += chunk.text
                            message_placeholder.markdown(temp_guide_text + "▌")
                    message_placeholder.markdown(temp_guide_text)
                    success = True
                    break 
                except ResourceExhausted:
                    continue
            
            if success:
                st.session_state.guide_text = temp_guide_text
                with st.spinner("Generating audio narration..."):
                    audio_file = generate_audio(clean_for_audio(temp_guide_text), tts_lang)
                    st.session_state.guide_audio = audio_file.getvalue() 
                st.session_state.camera_active = False
                st.session_state.pending_image = None
                st.rerun()
            else:
                st.error("⚠️ Rate limit reached.")
        except Exception as e:
            st.error(f"⚠️ Error: {e}")

    # Guide Display & Inline Follow-up
    if st.session_state.guide_text:
        st.write("---")
        st.write("### Your Latest Guide:")
        st.markdown(st.session_state.guide_text)
        if st.session_state.guide_audio:
            st.audio(st.session_state.guide_audio, format='audio/mp3')
            
        st.write("#### Have a follow-up question?")
        colA, colB = st.columns([4, 1])
        with colA:
            photo_q = st.text_input("Ask about this landmark...", key="photo_q", label_visibility="collapsed")
        with colB:
            ask_btn = st.button("Ask")
            
        if ask_btn and photo_q:
            with st.spinner("Thinking..."):
                genai.configure(api_key=api_keys[0])
                model = genai.GenerativeModel('gemini-3.5-flash-lite')
                history = f"AI Guide Output: {st.session_state.guide_text}\nUser Question: {photo_q}"
                ans = model.generate_content(f"{history}\nAnswer strictly in {target_lang}.").text
                st.info(ans)

# --- TAB 2: Location-Based Personal Recommendations & Events ---
with tab2:
    st.header("What's Around Me?")
    
    # Inline Location UX
    if not st.session_state.lat:
        st.warning("📍 I need your location to find nearby places.")
        location = streamlit_geolocation()
        if location and location.get('latitude'):
            st.session_state.lat = location['latitude']
            st.session_state.lon = location['longitude']
            st.rerun()
            
    custom_search = st.text_input("Looking for something specific?", placeholder="e.g., traditional knife forging, hidden matcha cafes, vintage kimonos...")
    event_count = st.slider("How many options do you want?", min_value=3, max_value=10, value=5)
    
    col1, col2, col3 = st.columns(3)
    with col1: want_food = st.button("🍽️ Visit & Eat")
    with col2: want_events = st.button("🎉 Trending Events")
    with col3: want_custom = st.button("🔍 Find Custom")

    trigger = "food" if want_food else "events" if want_events else "custom" if want_custom and custom_search else None
    if want_custom and not custom_search:
        st.warning("Please type something in the custom search box first!")

    if trigger and st.session_state.lat:
        with st.spinner(f"Scouting the live web (in {target_lang})..."):
            loc_context = get_location_context()
            current_date = datetime.now().strftime("%A, %B %d, %Y")
            success = False
            
            for key in api_keys:
                try:
                    genai.configure(api_key=key)
                    model_lite = genai.GenerativeModel('gemini-3.5-flash-lite')
                    model_heavy = genai.GenerativeModel('gemini-3.5-flash')
                    
                    if trigger == "food":
                        pref = f"Food: {', '.join(USER_PREFERENCES['food'])}. Activities: {', '.join(USER_PREFERENCES['activities'])}."
                        prompt = f"{loc_context}\nSuggest {event_count} places to visit and eat nearby tailoring to: {pref}.\nAnswer in {target_lang}."
                        response = model_lite.generate_content(prompt).text
                        st.session_state.raw_search_data = "No live web search used for food."
                    else:
                        city_name = model_lite.generate_content(f"Based on {loc_context}, what city am I in? Reply ONLY with the city name.").text.strip()
                        
                        # AI Keyword Translation to avoid the "light show" vs "illumination" mismatch
                        if trigger == "events":
                            search_query = f"events festivals popups illuminations {city_name} today {current_date}"
                        else:
                            smart_keywords = model_lite.generate_content(f"Translate this intent into the best Google search keywords for Japan: '{custom_search}'").text.strip()
                            search_query = f"{smart_keywords} {city_name}"
                            
                        live_web_data = fetch_live_search_tavily(search_query, tavily_key)
                        st.session_state.raw_search_data = f"**Query Sent:** {search_query}\n\n**Raw Results:**\n{live_web_data}"
                        
                        prompt = f"""
                        {loc_context} (City: {city_name})
                        Today's date is {current_date}. 
                        Raw live internet data: {live_web_data}
                        
                        Based on your internal knowledge AND the live web data, find {event_count} highly relevant recommendations matching: '{custom_search if custom_search else "trending seasonal events and pop-ups"}'.
                        Write the response strictly in {target_lang}.
                        """
                        response = model_heavy.generate_content(prompt).text
                        
                    st.markdown(response)
                    st.session_state.chat_history.append({"role": "user", "content": f"Find: {trigger}"})
                    st.session_state.chat_history.append({"role": "assistant", "content": response})
                    success = True
                    break
                except ResourceExhausted:
                    continue
            
            if not success:
                st.error("⚠️ Rate limit reached.")

    # Transparency Dropdown
    if st.session_state.raw_search_data:
        with st.expander("🔍 See Raw Search Results (Debug)"):
            st.write(st.session_state.raw_search_data)

# --- TAB 3: Persistent Chat ---
with tab3:
    st.header("Ask Questions")
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
    if user_question := st.chat_input("E.g., What time does the restaurant open?"):
        with st.chat_message("user"): st.markdown(user_question)
        st.session_state.chat_history.append({"role": "user", "content": user_question})
        
        history = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.chat_history[-5:]])
        with st.spinner("Thinking..."):
            for key in api_keys:
                try:
                    genai.configure(api_key=key)
                    model = genai.GenerativeModel('gemini-3.5-flash-lite')
                    ans = model.generate_content(f"{get_location_context()}\nHistory:\n{history}\nAnswer the user in {target_lang}.").text
                    with st.chat_message("assistant"): st.markdown(ans)
                    st.session_state.chat_history.append({"role": "assistant", "content": ans})
                    break
                except ResourceExhausted:
                    continue
