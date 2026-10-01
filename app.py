import streamlit as st
import google.generativeai as genai
from gtts import gTTS
from io import BytesIO
from PIL import Image
from datetime import datetime
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
    """Converts text to speech and returns an audio byte stream."""
    tts = gTTS(text=text, lang=lang_code, slow=False)
    fp = BytesIO()
    tts.write_to_fp(fp)
    fp.seek(0)
    return fp

def get_location_context():
    """Formats the GPS coordinates if available."""
    if st.session_state.get('lat') and st.session_state.get('lon'):
        return f"Current Location: {st.session_state.lat} Latitude, {st.session_state.lon} Longitude."
    return "Location unknown."

def clean_for_audio(text):
    """Removes markdown formatting so the text-to-speech sounds natural."""
    return text.replace("*", "").replace("#", "").replace('"', "").replace("_", "")

# -----------------------------------------
# 3. APP INITIALIZATION & SIDEBAR
# -----------------------------------------
st.set_page_config(page_title="Personal AI Guide", layout="wide")
st.title("🌍 My Personal AI Tour Guide")

# Initialize session states
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

with st.sidebar:
    st.header("⚙ Setup & Context")
    
    api_keys = st.secrets.get("GEMINI_API_KEYS", [])
    if not api_keys:
        manual_key = st.text_input("Enter Gemini API Key", type="password")
        if manual_key:
            api_keys = [manual_key]
            
    if not api_keys:
        st.warning("Please enter your Gemini API Key in the sidebar to begin.")
        st.stop()
    
    st.subheader("📍 Where am I?")
    st.write("Tap below to share your location for nearby recommendations.")
    location = streamlit_geolocation()
    if location and location.get('latitude'):
        st.session_state.lat = location['latitude']
        st.session_state.lon = location['longitude']
        st.success("Location locked!")
        
    st.subheader("🌐 Language / שפה")
    lang_choice = st.radio("Select your preferred language:", ["English", "Hebrew (עברית)"])

if lang_choice == "English":
    target_lang = "English"
    tts_lang = "en"
else:
    target_lang = "Hebrew"
    tts_lang = "iw" 

# -----------------------------------------
# 4. MAIN INTERFACE (TABS)
# -----------------------------------------
tab1, tab2, tab3 = st.tabs(["📸 Photo Guide", "🧭 Explore Nearby", "💬 Chat & Ask"])

# --- TAB 1: Photo & Audio Guide ---
with tab1:
    st.header("Scan a Landmark")
    
    if st.button("📷 Open / Close Camera"):
        st.session_state.camera_active = not st.session_state.camera_active
        st.rerun()
        
    image_source = None
    trigger_generation = False
    
    if st.session_state.camera_active:
        st.info("💡 **Tip:** Tap directly on the camera video feed to snap your photo.")
        camera_photo = back_camera_input()
        
        if camera_photo:
            image_source = camera_photo
            # If this is a brand new photo, trigger the AI automatically!
            if st.session_state.last_image_id != camera_photo.getvalue():
                st.session_state.last_image_id = camera_photo.getvalue()
                trigger_generation = True
    else:
        uploaded_file = st.file_uploader("Or upload from your camera roll", type=["jpg", "jpeg", "png"])
        if uploaded_file:
            image_source = uploaded_file
            # For manual uploads, we keep the button so you can confirm the right file
            if st.button("Generate Audio Guide"):
                trigger_generation = True

    if image_source and trigger_generation:
        image = Image.open(image_source)
        try:
            loc_context = get_location_context()
            prompt = f"""
            {loc_context}
            Act as an expert, engaging tour guide. Identify the landmark or subject in this image. 
            Provide a 2-minute fascinating historical overview. End with one interesting fact.
            Make the tone conversational and easy to listen to.
            Write the entire response strictly in {target_lang}.
            """
            
            st.write("### Generating Your Guide...")
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
                    st.toast("Key limit reached, swapping to backup...", icon="🔄")
                    continue
            
            if not success:
                st.error("⚠️ Rate limit reached. Wait 60 seconds or swap keys in Streamlit Secrets.")
            else:
                # SAVE STATE PERMANENTLY
                st.session_state.guide_text = temp_guide_text
                
                with st.spinner("Generating audio narration..."):
                    cleaned_text = clean_for_audio(temp_guide_text)
                    audio_file = generate_audio(cleaned_text, tts_lang)
                    st.session_state.guide_audio = audio_file.getvalue() 
                
                # Auto-close the camera to clean up the screen, then refresh
                st.session_state.camera_active = False
                st.rerun()
    
        except Exception as e:
            st.error(f"⚠️ An unexpected error occurred. \n\n**Error Details:** {e}")

    # ALWAYS display the saved guide if it exists
    if st.session_state.guide_text:
        st.write("---")
        st.write("### Your Latest Guide:")
        st.markdown(st.session_state.guide_text)
        if st.session_state.guide_audio:
            st.audio(st.session_state.guide_audio, format='audio/mp3')

# --- TAB 2: Location-Based Personal Recommendations & Events ---
with tab2:
    st.header("What's Around Me?")
    
    event_count = st.slider("How many events do you want to find?", min_value=3, max_value=10, value=8)
    
    col1, col2 = st.columns(2)
    with col1:
        want_food = st.button("🍽️ Visit & Eat")
    with col2:
        want_events = st.button("🎉 Trending Events")

    if want_food or want_events:
        if not st.session_state.lat:
            st.warning("Please allow location access in the sidebar first!")
        else:
            with st.spinner(f"Scouting the live web for your area (in {target_lang})..."):
                loc_context = get_location_context()
                
                if want_food:
                    pref_text = f"Food preferences: {', '.join(USER_PREFERENCES['food'])}. Activity preferences: {', '.join(USER_PREFERENCES['activities'])}."
                    prompt = f"""
                    {loc_context}
                    You are a highly personalized travel concierge. Based ONLY on the exact coordinates provided, 
                    suggest 2 places to visit and 2 places to eat nearby. 
                    Tailor these suggestions specifically to the following user preferences: {pref_text}.
                    Explain exactly why these nearby spots fit their specific tastes.
                    Write the entire response strictly in {target_lang}.
                    """
                else:
                    current_date = datetime.now().strftime("%A, %B %d, %Y")
                    prompt = f"""
                    {loc_context}
                    Today's date is {current_date}. 
                    Act as a local event scout with up-to-the-minute knowledge. Find {event_count} trending, pop-up, or special events (festivals, light shows, night markets, exhibitions, nightlife) happening around these exact coordinates over the next few days.
                    Prioritize temporary or seasonal events happening right now.
                    For each event, include a brief description and the estimated travel time/ride time from the current location.
                    Write the entire response strictly in {target_lang}.
                    """
                
                success = False
                for key in api_keys:
                    try:
                        genai.configure(api_key=key)
                        model = genai.GenerativeModel('gemini-3.5-flash-lite')
                        
                        if want_food:
                            response = model.generate_content(prompt)
                        else:
                            response = model.generate_content(prompt, tools="google_search_retrieval")
                            
                        recommendations = response.text
                        success = True
                        break
                    except ResourceExhausted:
                        st.toast("Key limit reached, swapping to backup...", icon="🔄")
                        continue
                
                if not success:
                    st.error("⚠️ Rate limit reached. Wait 60 seconds or swap keys in Streamlit Secrets.")
                else:
                    st.session_state.chat_history.append({"role": "user", "content": "What is around me?"})
                    st.session_state.chat_history.append({"role": "assistant", "content": recommendations})
                    st.markdown(recommendations)

# --- TAB 3: Persistent Chat ---
with tab3:
    st.header("Ask Questions")
    st.write("Ask follow-up questions about the tour guide audio, the recommendations, or anything else nearby.")
    
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
    if user_question := st.chat_input("E.g., What time does the restaurant open?"):
        with st.chat_message("user"):
            st.markdown(user_question)
            
        st.session_state.chat_history.append({"role": "user", "content": user_question})
        
        history_text = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.chat_history[-5:]])
        loc_context = get_location_context()
        
        chat_prompt = f"""
        {loc_context}
        Here is the recent conversation history:
        {history_text}
        
        Answer the user's latest question as a helpful tour guide.
        Write the entire response strictly in {target_lang}.
        """
        
        with st.spinner("Thinking..."):
            success = False
            for key in api_keys:
                try:
                    genai.configure(api_key=key)
                    model = genai.GenerativeModel('gemini-3.5-flash-lite')
                    response = model.generate_content(chat_prompt)
                    answer = response.text
                    success = True
                    break
                except ResourceExhausted:
                    st.toast("Key limit reached, swapping to backup...", icon="🔄")
                    continue
            
        if not success:
            st.error("⚠️ Rate limit reached. Wait 60 seconds or swap keys in Streamlit Secrets.")
        else:
            with st.chat_message("assistant"):
                st.markdown(answer)
            st.session_state.chat_history.append({"role": "assistant", "content": answer})
