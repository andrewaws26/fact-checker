import streamlit as st
from tavily import TavilyClient
import re

# --- Page Configuration ---
st.set_page_config(page_title="NewsGrader AI", page_icon="⚖️", layout="centered")

# Custom CSS for the big Letter Grade
st.markdown("""
    <style>
    .letter-grade {
        font-size: 100px;
        font-weight: bold;
        text-align: center;
        margin-bottom: 0px;
    }
    .verdict-text {
        font-size: 24px;
        text-align: center;
        font-weight: bold;
        margin-top: -20px;
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- Sidebar Configuration ---
with st.sidebar:
    st.title("⚙️ Settings")
    tavily_key = st.text_input("Tavily API Key", type="password")
    st.info("This app uses Tavily's Research Agent to cross-reference news claims with the live web.")

# --- Helper Functions ---
def get_grade_styling(report_text):
    """Extracts the letter grade from the AI report and returns styling info."""
    # Look for a single letter A, B, C, D, or F followed by a space or dash
    match = re.search(r'#\s*([A-DF])', report_text)
    grade = match.group(1) if match else "N/A"
    
    colors = {"A": "#2ecc71", "B": "#3498db", "C": "#f1c40f", "D": "#e67e22", "F": "#e74c3c", "N/A": "#95a5a6"}
    return grade, colors.get(grade, "#95a5a6")

def run_news_audit(url, api_key):
    tavily = TavilyClient(api_key=api_key)
    
    # Using your optimized playground prompt
    prompt = f"""
    Role: Consumer Protection Auditor & News Critic.
    Task: Grade the following article for a general audience: {url}

    Instructions:
    1. THE VIBE: Use clear, simple language. No jargon.
    2. RESEARCH: Search for at least 3 outside sources to see if they agree or disagree.
    3. THE GRADING SCALE: A (Verified), B (Mostly True), C (Mixed/Spin), D (Major Red Flags), F (False).

    FINAL OUTPUT FORMAT:
    # [Letter Grade]
    ## 🔍 The Quick Verdict
    [One-sentence summary]
    
    ## 🛑 The Red Flags (The Bad)
    - [Point 1]
    
    ## ✅ The Verified Facts (The Good)
    - [Point 1]
    
    ## 🔗 Sources Found
    [Links to outside sources used for verification]
    """
    
    # Trigger the autonomous research agent
    return tavily.research(query=prompt)

# --- Main App UI ---
st.title("⚖️ NewsGrader AI")
st.write("Paste a link to any news article. We'll audit it against the web and give it a grade.")

url_input = st.text_input("Article URL", placeholder="https://www.example.com/news-story")

if st.button("Audit Article", use_container_width=True):
    if not tavily_key:
        st.warning("Please enter your Tavily API Key in the sidebar.")
    elif not url_input:
        st.error("Please provide a valid URL.")
    else:
        # Use st.status to replicate the 'Reasoning Trace' feel
        with st.status("🕵️ Auditor is investigating...", expanded=True) as status:
            try:
                st.write("Extracting claims from article...")
                st.write("Searching for primary sources and counter-evidence...")
                
                report = run_news_audit(url_input, tavily_key)
                
                status.update(label="Audit Complete!", state="complete", expanded=False)
                
                # --- Display Results ---
                grade, color = get_grade_styling(report)
                
                st.divider()
                
                # Visual Grade Header
                st.markdown(f"<div class='letter-grade' style='color: {color};'>{grade}</div>", unsafe_allow_html=True)
                
                # Full Report
                st.markdown(report)
                
            except Exception as e:
                st.error(f"An error occurred: {e}")
