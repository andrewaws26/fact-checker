import streamlit as st
from tavily import TavilyClient
import requests
import time
import json

# --- Page Config ---
st.set_page_config(page_title="NewsGrader Pro", page_icon="⚖️", layout="centered")

st.markdown("""
    <style>
    .letter-grade { font-size: 100px; font-weight: bold; text-align: center; margin-bottom: 0px; }
    .verdict-box { background-color: #f0f2f6; padding: 20px; border-radius: 10px; text-align: center; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- Sidebar: Settings ---
with st.sidebar:
    st.title("⚙️ Settings")
    
    # Hybrid Key: Secrets first, then UI override
    default_key = st.secrets.get("TAVILY_API_KEY", "")
    api_key = st.text_input("Tavily API Key", value=default_key, type="password")
    
    st.divider()
    research_mode = st.radio("Depth:", ["Mini (Fast)", "Pro (Deep Audit)"])
    selected_model = "mini" if "Mini" in research_mode else "pro"

# --- The Strict JSON Schema ---
# This tells Tavily EXACTLY how to format the answer. No more Regex!
AUDIT_SCHEMA = {
    "properties": {
        "letter_grade": {
            "type": "string",
            "enum": ["A", "B", "C", "D", "F"],
            "description": "The overall truthfulness grade."
        },
        "one_sentence_verdict": {
            "type": "string",
            "description": "A concise summary of the findings."
        },
        "red_flags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of lies, distortions, or missing context."
        },
        "verified_facts": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of claims that are true and verified."
        }
    },
    "required": ["letter_grade", "one_sentence_verdict", "red_flags", "verified_facts"]
}

# --- Core Logic ---
def start_audit_task(url, key, model):
    """Starts the research job and returns the Ticket ID (or result if fast)."""
    client = TavilyClient(api_key=key)
    
    prompt = f"Audit this article for accuracy: {url}"
    
    try:
        # We pass the schema here to force JSON output
        response = client.research(
            input=prompt,
            model=model,
            output_schema=AUDIT_SCHEMA
        )
        return response
    except Exception as e:
        return {"error": str(e)}

def poll_for_result(request_id, key):
    """Manually checks the /research/{id} endpoint from your docs."""
    url = f"https://api.tavily.com/research/{request_id}"
    headers = {"Authorization": f"Bearer {key}"}
    
    try:
        # Simple GET request based on the OpenAPI spec you provided
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            return res.json()
    except:
        pass
    return {"status": "error"}

# --- Main UI ---
st.title("⚖️ NewsGrader Pro")
st.caption("Powered by Tavily Research API • Structured Data")

url_input = st.text_input("Article URL", placeholder="https://www.example.com/...")

if st.button("Run Audit"):
    if not api_key:
        st.error("Please provide an API Key.")
        st.stop()
    
    if not url_input:
        st.error("Please provide a URL.")
        st.stop()

    # 1. Start the Job
    with st.status("🚀 Initializing Agent...", expanded=True) as status:
        initial_res = start_audit_task(url_input, api_key, selected_model)
        
        # Check for immediate errors
        if "error" in initial_res:
            st.error(f"Failed to start: {initial_res['error']}")
            st.stop()
            
        # 2. Handle Sync Result (Mini often finishes instantly)
        if initial_res.get("status") == "completed":
            final_data = initial_res.get("content", {})
            # If content is string (json string), parse it
            if isinstance(final_data, str):
                try: final_data = json.loads(final_data)
                except: pass
            
            status.update(label="Audit Complete!", state="complete", expanded=False)

        # 3. Handle Async Result (Pro needs polling)
        else:
            req_id = initial_res.get("request_id")
            if not req_id:
                st.error("No Request ID returned.")
                st.stop()
                
            # Polling Loop (Max 5 mins for Pro)
            progress_bar = st.progress(0, text="🕵️ Agent is reading sources...")
            final_data = None
            
            for i in range(60): # 60 * 5s = 5 minutes
                time.sleep(5)
                
                # Update UI
                pct = min((i*2)/100, 0.95)
                progress_bar.progress(pct, text=f"🧠 Analyzing claims ({i*5}s elapsed)...")
                
                # Check API
                poll_data = poll_for_result(req_id, api_key)
                
                if poll_data.get("status") == "completed":
                    final_data = poll_data.get("content")
                    # Should be a dict because of output_schema, but safety first
                    if isinstance(final_data, str):
                         try: final_data = json.loads(final_data)
                         except: pass
                    break
                
                if poll_data.get("status") == "failed":
                    st.error("Research task failed on server side.")
                    st.stop()
            
            progress_bar.empty()
            if not final_data:
                st.error("Timed out waiting for Pro agent.")
                st.stop()
            
            status.update(label="Audit Complete!", state="complete", expanded=False)

    # --- 4. Display Structured Results ---
    # Now we assume final_data is a dictionary matching our Schema
    
    if isinstance(final_data, dict):
        grade = final_data.get("letter_grade", "N/A")
        verdict = final_data.get("one_sentence_verdict", "No verdict available.")
        bad_stuff = final_data.get("red_flags", [])
        good_stuff = final_data.get("verified_facts", [])
        
        # Color Logic
        grade_colors = {"A": "#2ecc71", "B": "#3498db", "C": "#f1c40f", "D": "#e67e22", "F": "#e74c3c"}
        color = grade_colors.get(grade, "#95a5a6")
        
        st.divider()
        
        # The Hero Section
        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown(f"<div class='letter-grade' style='color: {color};'>{grade}</div>", unsafe_allow_html=True)
        with col2:
            st.markdown(f"### 🔍 Auditor's Verdict")
            st.info(verdict)

        # The Details
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### 🛑 Red Flags")
            if not bad_stuff: st.write("No major red flags found.")
            for flag in bad_stuff:
                st.error(f"• {flag}")
                
        with c2:
            st.markdown("### ✅ Verified Facts")
            if not good_stuff: st.write("No verified facts found.")
            for fact in good_stuff:
                st.success(f"• {fact}")

    else:
        st.warning("Raw Output (Could not parse JSON):")
        st.write(final_data)
