import streamlit as st
import google.generativeai as genai
from gtts import gTTS
from io import BytesIO
from PIL import Image
from streamlit_geolocation import streamlit_geolocation
from streamlit_back_camera_input import back_camera_input

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
    st.header("⚙️️ Setup & Context")
    api_key = st.text_input("Enter Gemini API Key", type="password")
    
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

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-3.5-flash-lite')

# -----------------------------------------
# 4. MAIN INTERFACE (TABS)
# -----------------------------------------
tab1, tab2, tab3 = st.tabs(["📸 Photo Guide", "🧭 Explore Nearby", "💬 Chat & Ask"])

# --- TAB 1: Photo & Audio Guide ---# --- TAB 1: Photo & Audio Guide ---
with tab1:
    st.header("Scan a Landmark")
    st.write("Upload a photo or open the camera to see what's around you.")
    
    # 1. HIDE CAMERA UNTIL CLICKED
    camera_photo = None
    with st.expander("📷 Tap to Open Camera"):
        # The mobile view will have a "flip camera" icon to switch to the rear lens
        camera_photo = back_camera_input()
        
    uploaded_file = st.file_uploader("Or upload from your camera roll", type=["jpg", "jpeg", "png"])
        
    image_source = camera_photo if camera_photo else uploaded_file

    if image_source and st.button("Generate Audio Guide"):
        image = Image.open(image_source)
        st.image(image, use_container_width=True)
        
        # 4. ERROR HANDLING BLOCK
        try:
            loc_context = get_location_context()
            
            # 3. ADAPTIVE PROMPT
            prompt = f"""
            {loc_context}
            Act as a helpful, conversational travel companion. Look at this image and respond based on what it is:
            - If it's a landmark or building, give a brief, interesting history.
            - If it's a sign, menu, or text, explain or translate it.
            - If it's food or nature, tell me interesting facts about it.
            Keep it highly relevant to the specific image. Do not use a rigid structure. Keep it under 3 paragraphs.
            Write the entire response strictly in {target_lang}.
            """
            
            st.write("### Your Guide:")
            # 2. STREAMING FOR INSTANT SPEED (Manual Loop Fix)
        response = model.generate_content([prompt, image], stream=True)
        
        message_placeholder = st.empty()
        guide_text = ""
        
        # Stream the text to the screen chunk by chunk
        for chunk in response:
            if chunk.text:
                guide_text += chunk.text
                message_placeholder.markdown(guide_text + "▌")
        
        # Remove the blinking cursor when finished
        message_placeholder.markdown(guide_text)
        
        # Save to chat history
        st.session_state.chat_history.append({"role": "user", "content": f"Tell me about the landmark in the photo I just uploaded. Answer in {target_lang}."})
        st.session_state.chat_history.append({"role": "assistant", "content": guide_text})
        
        # Generate and play audio (Now guaranteed to be a plain string)
        with st.spinner("Generating audio narration..."):
            audio_file = generate_audio(guide_text, tts_lang)
            st.audio(audio_file, format='audio/mp3')
                
        except Exception as e:
            # If the API crashes, it will show this clear red error box
            st.error(f"⚠️ The AI encountered an error. If this happened instantly, check your API key and ensure the model name is 'gemini-2.5-flash'. \n\n**Error Details:** {e}")

# --- TAB 2: Location-Based Personal Recommendations ---
with tab2:
    st.header("What's Around Me?")
    if st.button("Find Places to Visit & Eat"):
        if not st.session_state.lat:
            st.warning("Please allow location access in the sidebar first!")
        else:
            with st.spinner(f"Scouting the area based on your preferences (in {target_lang})..."):
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
            response = model.generate_content(chat_prompt)
            answer = response.text
            
        with st.chat_message("assistant"):
            st.markdown(answer)
            
        st.session_state.chat_history.append({"role": "assistant", "content": answer})
