import streamlit as st
from tavily import TavilyClient
import re

# --- Page Configuration ---
st.set_page_config(page_title="NewsGrader AI", page_icon="⚖️", layout="centered")

# Custom CSS for the big Letter Grade display
st.markdown("""
    <style>
    .letter-grade {
        font-size: 100px;
        font-weight: bold;
        text-align: center;
        margin-bottom: 0px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- Security: UI-Based Key Input ---
with st.sidebar:
    st.title("⚙️ Settings")
    # Try to get from secrets first, otherwise empty
    default_key = st.secrets.get("TAVILY_API_KEY", "")
    
    user_key = st.text_input(
        "Enter Tavily API Key", 
        value=default_key, 
        type="password",
        help="Get your key at app.tavily.com"
    )
    st.info("This app uses Tavily's Research Agent to cross-reference news claims.")

# --- Helper Functions ---
def get_grade_styling(report_text):
    """Safely extracts the grade from text."""
    # Ensure we are dealing with a string
    text_to_search = str(report_text) 
    match = re.search(r'#\s*([A-DF])', text_to_search)
    grade = match.group(1) if match else "N/A"
    colors = {"A": "#2ecc71", "B": "#3498db", "C": "#f1c40f", "D": "#e67e22", "F": "#e74c3c", "N/A": "#95a5a6"}
    return grade, colors.get(grade, "#95a5a6")

def run_news_audit(url, api_key):
    tavily = TavilyClient(api_key=api_key)
    
    audit_prompt = f"""
    Role: Consumer Protection Auditor & News Critic.
    Task: Grade the following article for a general audience: {url}
    Instructions: Provide a # [Letter Grade] at the very top, then 'The Quick Verdict', 'The Red Flags', and 'Verified Facts'. 
    Use simple language.
    """
    
    # Trigger the agent
    response = tavily.research(input=audit_prompt)
    
    # If the response is a dictionary (common with the research endpoint), 
    # we convert it to a string for display and regex processing.
    if isinstance(response, dict):
        # Most Tavily Agent responses put the main text in 'content' or 'output'
        return response.get("output", str(response))
    return response

# --- Main App UI ---
st.title("⚖️ NewsGrader AI")
st.write("Audit any news link. Enter your key in the sidebar to start.")

url_input = st.text_input("Article URL", placeholder="https://www.example.com/news-story")

if st.button("Audit Article", use_container_width=True):
    if not user_key:
        st.error("Please enter a Tavily API Key in the sidebar.")
    elif not url_input:
        st.error("Please provide a valid news URL.")
    else:
        with st.status("🕵️ Auditor is investigating...", expanded=True) as status:
            try:
                st.write("Extracting claims and searching the live web...")
                
                # Run the audit (now handles the dictionary error)
                report_content = run_news_audit(url_input, user_key)
                
                status.update(label="Audit Complete!", state="complete", expanded=False)
                
                # --- Display Results ---
                grade, color = get_grade_styling(report_content)
                
                st.divider()
                st.markdown(f"<div class='letter-grade' style='color: {color};'>{grade}</div>", unsafe_allow_html=True)
                st.markdown(report_content)
                
            except Exception as e:
                # Improved error reporting
                st.error(f"Error during audit: {e}")
                if "invalid api key" in str(e).lower():
                    st.info("Your API key seems incorrect. Please double-check it in the sidebar.")
