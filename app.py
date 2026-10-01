import streamlit as st
import google.generativeai as genai
from gtts import gTTS
from io import BytesIO
from PIL import Image
from streamlit_geolocation import streamlit_geolocation
from streamlit_back_camera_input import back_camera_input
from google.api_core.exceptions import ResourceExhausted

# -----------------------------------------
# 1. ARCHITECTURE & EXTENSIBILITY SETUP
# -----------------------------------------
# Centralized preferences block to prepare for future scope expansion.
USER_PREFERENCES = {
    "food": ["Charcuterie", "Artisan pastries", "Premium burgers", "Local culinary workshops"],
    "activities": ["Escape rooms", "Trivia and pub quizzes", "Theater performances", "Orienteering"]
}

# -----------------------------------------
# 2. HELPER FUNCTIONS
# -----------------------------------------
def generate_audio(text, lang_code):
    """Converts text to speech and returns an audio byte stream in the selected language."""
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

# Initialize session state for memory
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "lat" not in st.session_state:
    st.session_state.lat = None
if "lon" not in st.session_state:
    st.session_state.lon = None

with st.sidebar:
    st.header("⚙ Setup & Context")
    
    # Look for the list of keys. If it doesn't exist, return an empty list.
    api_keys = st.secrets.get("GEMINI_API_KEYS", [])
    
    # If the list is empty, force the user to type one in manually
    if not api_keys:
        manual_key = st.text_input("Enter Gemini API Key", type="password")
        if manual_key:
            api_keys = [manual_key] # Turn it into a list so the rest of the code works
            
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

# Set Language Variables
if lang_choice == "English":
    target_lang = "English"
    tts_lang = "en"
else:
    target_lang = "Hebrew"
    tts_lang = "iw" 

if not api_key:
    st.warning("Please enter your Gemini API Key in the sidebar to begin.")
    st.stop()

model = genai.GenerativeModel('gemini-3.5-flash-lite')

# -----------------------------------------
# 4. MAIN INTERFACE (TABS)
# -----------------------------------------
tab1, tab2, tab3 = st.tabs(["📸 Photo Guide", "🧭 Explore Nearby", "💬 Chat & Ask"])

# --- TAB 1: Photo & Audio Guide ---
with tab1:
    st.header("Scan a Landmark")
    st.write("Upload a photo or open the camera to see what's around you.")
    
    # 1. COMPLETELY UNLOAD CAMERA UNTIL CHECKED
    camera_photo = None
    if st.checkbox("📷 Turn on Camera"):
        camera_photo = back_camera_input()
        
    uploaded_file = st.file_uploader("Or upload from your camera roll", type=["jpg", "jpeg", "png"])
        
    image_source = camera_photo if camera_photo else uploaded_file

    if image_source and st.button("Generate Audio Guide"):
        image = Image.open(image_source)
        # Note: st.image() is completely removed here to save screen space
        try:
            loc_context = get_location_context()
            prompt = f"""
            {loc_context}
            Act as an expert, engaging tour guide... [keep your prompt here]
            """
            
            st.write("### Your Guide:")
            
            message_placeholder = st.empty()
            guide_text = ""
            
            # Fetch the list of keys from secrets
            api_keys = st.secrets.get("GEMINI_API_KEYS", [])
            success = False
            
            # 1. LOOP THROUGH THE KEYS
            for key in api_keys:
                try:
                    # Configure the AI with the current key in the loop
                    genai.configure(api_key=key)
                    model = genai.GenerativeModel('gemini-3.5-flash-lite')
                    
                    # Attempt to generate text
                    response = model.generate_content([prompt, image], stream=True)
                    
                    for chunk in response:
                        if chunk.text:
                            guide_text += chunk.text
                            message_placeholder.markdown(guide_text + "▌")
                    
                    message_placeholder.markdown(guide_text)
                    success = True
                    break # Success! Break out of the loop so we don't use the next key
                    
                except ResourceExhausted:
                    # 2. CATCH RATE LIMITS
                    # If this key is exhausted, show a tiny toast notification and loop to the next key
                    st.toast("Key limit reached, swapping to backup key...", icon="🔄")
                    continue
            
            # 3. IF ALL KEYS FAIL
            if not success:
                st.error("⚠️ All provided API keys have reached their daily limits. Try again tomorrow.")
            else:
                # Save to history and generate audio only if successful
                st.session_state.chat_history.append({"role": "user", "content": f"Tell me about the landmark in the photo I just uploaded. Answer in {target_lang}."})
                st.session_state.chat_history.append({"role": "assistant", "content": guide_text})
                
                with st.spinner("Generating audio narration..."):
                    cleaned_text = clean_for_audio(guide_text)
                    audio_file = generate_audio(cleaned_text, tts_lang)
                    st.audio(audio_file, format='audio/mp3')
    
        except Exception as e:
            st.error(f"⚠️ An unexpected error occurred. \n\n**Error Details:** {e}")

# --- TAB 2: Location-Based Personal Recommendations ---
with tab2:
    st.header("What's Around Me?")
    if st.button("Find Places to Visit & Eat"):
        if not st.session_state.lat:
            st.warning("Please allow location access in the sidebar first!")
        else:
            with st.spinner(f"Scouting the area based on your preferences (in {target_lang})..."):
                genai.configure(api_key=api_keys[0])
                loc_context = get_location_context()
                pref_text = f"Food preferences: {', '.join(USER_PREFERENCES['food'])}. Activity preferences: {', '.join(USER_PREFERENCES['activities'])}."
                
                prompt = f"""
                {loc_context}
                You are a highly personalized travel concierge. Based ONLY on the exact coordinates provided, 
                suggest 2 places to visit and 2 places to eat nearby. 
                Tailor these suggestions specifically to the following user preferences: {pref_text}.
                Explain exactly why these nearby spots fit their specific tastes.
                Write the entire response strictly in {target_lang}.
                """
                
                response = model.generate_content(prompt)
                recommendations = response.text
                
                # Save to chat history
                st.session_state.chat_history.append({"role": "user", "content": f"What is around me based on my location and preferences? Answer in {target_lang}."})
                st.session_state.chat_history.append({"role": "assistant", "content": recommendations})
                
                st.markdown(recommendations)

# --- TAB 3: Persistent Chat ---
with tab3:
    st.header("Ask Questions")
    st.write("Ask follow-up questions about the tour guide audio, the recommendations, or anything else nearby.")
    
    # Display chat history
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
    # Chat Input
    if user_question := st.chat_input("E.g., What time does the restaurant open?"):
        with st.chat_message("user"):
            st.markdown(user_question)
            
        st.session_state.chat_history.append({"role": "user", "content": user_question})
        
        # Build prompt with history for context
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
            genai.configure(api_key=api_keys[0])
            response = model.generate_content(chat_prompt)
            answer = response.text
            
        with st.chat_message("assistant"):
            st.markdown(answer)
            
        st.session_state.chat_history.append({"role": "assistant", "content": answer})
