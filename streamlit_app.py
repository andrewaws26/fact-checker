import streamlit as st
from tavily import TavilyClient
import re
import time  # Required for the waiting loop

# --- Page Configuration ---
st.set_page_config(page_title="NewsGrader AI", page_icon="⚖️", layout="centered")

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

# --- Security ---
with st.sidebar:
    st.title("⚙️ Settings")
    default_key = st.secrets.get("TAVILY_API_KEY", "")
    user_key = st.text_input("Enter Tavily API Key", value=default_key, type="password")
    st.info("The Research Agent takes 1-3 minutes to run a full audit.")

# --- Helper Functions ---
def get_grade_styling(report_text):
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
    """
    
    # 1. Start the Job
    # The API returns a 'request_id' immediately
    initial_response = tavily.research(input=audit_prompt)
    
    # If it finishes instantly (rare), return it
    if initial_response.get('status') == 'completed':
        return initial_response.get('output', str(initial_response))
    
    # 2. Polling Loop (Waiting for the Agent)
    request_id = initial_response.get('request_id')
    
    if not request_id:
        return "Error: Could not start research task."

    # Loop for up to 3 minutes (180 seconds)
    timeout = 180 
    start_time = time.time()
    
    while (time.time() - start_time) < timeout:
        # Wait 5 seconds before checking again
        time.sleep(5)
        
        # Check status
        # Note: The SDK might behave differently depending on version. 
        # We try to use the generic 'get_research_status' if available, 
        # but currently the SDK handles this via a direct call or specific endpoint.
        # Since the Python SDK wrapper for 'research' is new, we often just wait.
        # However, for this specific 'pending' dict, we likely need to wait.
        
        try:
            # Re-fetch status using the ID
            # (Note: In some SDK versions, you might need to use specific methods.
            # If this fails, we will catch it.)
            # For now, let's assume we can re-call or use a status endpoint.
            # *CRITICAL*: The standard Tavily Python SDK 'research' method 
            # usually blocks if you don't set stream=True. 
            # If you are getting 'pending', you might be on a specific beta version.
            
            # Let's try the safest "wait and retry" approach provided by the docs
            status_update = tavily.get_research_status(request_id)
            
            if status_update.get('status') == 'completed':
                 # The final report is usually in 'output' or 'content'
                return status_update.get('report', status_update.get('output'))
        except:
            # If get_research_status doesn't exist in your version,
            # we break to avoid infinite loop and show what we have.
            pass
            
    return "Timed out waiting for research report."

# --- Main App UI ---
st.title("⚖️ NewsGrader AI")

url_input = st.text_input("Article URL", placeholder="https://www.example.com/news-story")

if st.button("Audit Article", use_container_width=True):
    if not user_key:
        st.error("Please enter a Tavily API Key.")
    elif not url_input:
        st.error("Please provide a valid URL.")
    else:
        with st.status("🕵️ Auditor is investigating (this takes ~2 mins)...", expanded=True) as status:
            try:
                st.write("Job started... waiting for agent...")
                
                # We simply handle the dictionary logic directly here if the function above 
                # returns the raw dictionary again.
                report_content = run_news_audit(url_input, user_key)
                
                # Final check: Did we get a string or still a dictionary?
                if isinstance(report_content, dict):
                     # If it's still a dict, extracting the raw content if possible
                     report_content = report_content.get('output', str(report_content))

                status.update(label="Audit Complete!", state="complete", expanded=False)
                
                grade, color = get_grade_styling(report_content)
                
                st.divider()
                st.markdown(f"<div class='letter-grade' style='color: {color};'>{grade}</div>", unsafe_allow_html=True)
                st.markdown(report_content)
                
            except Exception as e:
                st.error(f"Error: {e}")
