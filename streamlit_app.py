import streamlit as st
from tavily import TavilyClient
import time
import json
import re

# --- Page Config ---
st.set_page_config(page_title="NewsGrader Pro", page_icon="⚖️", layout="wide")

# --- CSS Styling ---
st.markdown("""
    <style>
    .letter-grade { 
        font-size: 80px; 
        font-weight: 800; 
        text-align: center; 
        line-height: 1;
        margin-bottom: 10px;
    }
    .metric-card {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 10px;
        padding: 20px;
        height: 100%;
    }
    </style>
    """, unsafe_allow_html=True)

# --- Helper: Robust JSON Parser ---
def clean_and_parse_json(raw_output):
    """
    Attempts to clean LLM output which often includes markdown 
    code fences (```json ... ```) before parsing.
    """
    if isinstance(raw_output, dict):
        return raw_output
        
    # Strip markdown code blocks if present
    text = str(raw_output)
    pattern = r"```json\s*(.*?)\s*```"
    match = re.search(pattern, text, re.DOTALL)
    
    if match:
        text = match.group(1)
        
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None

# --- Core Logic with Caching ---
# We cache this function so running the same URL twice is instant and free
@st.cache_data(show_spinner=False, ttl=3600)
def run_audit_process(url, api_key, model_selection):
    """
    Wraps the API call and polling logic. 
    Returns the final dictionary or raises an error.
    """
    client = TavilyClient(api_key=api_key)
    
    # Enhanced prompt to ensure external verification
    prompt = (
        f"Act as a strict Fact-Checker. Audit this article: {url}. "
        "Do NOT just summarize it. You must Cross-Reference claims against "
        "authoritative, external sources to verify accuracy. "
        "Be critical."
    )

    # Schema Definition
    audit_schema = {
        "properties": {
            "letter_grade": {"type": "string", "enum": ["A", "B", "C", "D", "F"]},
            "one_sentence_verdict": {"type": "string"},
            "red_flags": {"type": "array", "items": {"type": "string"}},
            "verified_facts": {"type": "array", "items": {"type": "string"}},
            "sources_used": {"type": "array", "items": {"type": "string"}} # Added this field
        },
        "required": ["letter_grade", "one_sentence_verdict", "red_flags", "verified_facts"]
    }

    try:
        # Start the task
        response = client.research(
            input=prompt,
            model=model_selection,
            output_schema=audit_schema
        )
    except Exception as e:
        return {"error": f"API Connection Failed: {str(e)}"}

    # Handle Synchronous Result (Mini)
    if response.get("status") == "completed":
        return clean_and_parse_json(response.get("content"))

    # Handle Asynchronous Result (Pro)
    req_id = response.get("request_id")
    if not req_id:
        return {"error": "No Request ID returned from API."}

    # Polling Loop
    for _ in range(60): # Max 5 mins
        time.sleep(5)
        try:
            # Note: We use the requests library manually here to poll
            poll_res = client.get_search_context(query=req_id) # Using a dummy call or direct request if client lacks poll
            # Since standard client might not expose 'poll', we revert to requests if needed:
            import requests
            poll_url = f"[https://api.tavily.com/research/](https://api.tavily.com/research/){req_id}"
            poll_resp = requests.get(poll_url, headers={"Authorization": f"Bearer {api_key}"})
            
            if poll_resp.status_code == 200:
                data = poll_resp.json()
                if data.get("status") == "completed":
                    return clean_and_parse_json(data.get("content"))
                if data.get("status") == "failed":
                    return {"error": "Task failed on Tavily server."}
        except Exception:
            pass
            
    return {"error": "Operation timed out."}

# --- Sidebar ---
with st.sidebar:
    st.title("⚙️ Settings")
    default_key = st.secrets.get("TAVILY_API_KEY", "")
    api_key = st.text_input("Tavily API Key", value=default_key, type="password")
    
    st.divider()
    research_mode = st.radio("Depth:", ["Mini (Fast)", "Pro (Deep Audit)"], index=0)
    selected_model = "mini" if "Mini" in research_mode else "pro"
    
    st.info("💡 **Pro Tip:** 'Mini' is good for quick fact checks. 'Pro' is better for deep-dives into long articles.")

# --- Main UI ---
st.title("⚖️ NewsGrader Pro")
st.caption("AI-Powered Truth & Accuracy Auditor")

# Using a Form ensures the page doesn't reload/reset when we click buttons
with st.form("audit_form"):
    url_input = st.text_input("Article URL", placeholder="[https://www.nytimes.com/](https://www.nytimes.com/)...")
    submitted = st.form_submit_button("Run Audit")

if submitted:
    if not api_key:
        st.error("⚠️ Please provide a Tavily API Key in the sidebar.")
        st.stop()
    if not url_input:
        st.error("⚠️ Please provide a URL.")
        st.stop()

    # Progress Indicator
    with st.status("🕵️ Agent is auditing sources...", expanded=True) as status:
        st.write("Initializing research agent...")
        final_data = run_audit_process(url_input, api_key, selected_model)
        
        if "error" in final_data:
            status.update(label="Audit Failed", state="error")
            st.error(final_data["error"])
            st.stop()
        else:
            status.update(label="Audit Complete!", state="complete", expanded=False)

    # --- Display Results ---
    if final_data:
        # Define Colors
        grade_map = {
            "A": ("#2ecc71", "High Accuracy"), 
            "B": ("#3498db", "Mostly Accurate"), 
            "C": ("#f1c40f", "Mixed Accuracy"), 
            "D": ("#e67e22", "Questionable"), 
            "F": ("#e74c3c", "Misleading/False")
        }
        
        grade = final_data.get("letter_grade", "C")
        color, label = grade_map.get(grade, ("#95a5a6", "Unknown"))
        
        st.divider()
        
        # Hero Section
        col1, col2 = st.columns([1, 4])
        with col1:
            st.markdown(f"""
            <div class='metric-card'>
                <div class='letter-grade' style='color: {color};'>{grade}</div>
                <div style='text-align: center; font-weight: bold;'>{label}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"### 🔍 Verdict")
            st.info(final_data.get("one_sentence_verdict", "No verdict provided."))
            # Optional: Display source count if available
            sources = final_data.get("sources_used", [])
            if sources:
                st.caption(f"📚 Verified against {len(sources)} external sources.")

        # Details Section
        st.divider()
        c1, c2 = st.columns(2)
        
        with c1:
            st.subheader("🛑 Red Flags & Omissions")
            flags = final_data.get("red_flags", [])
            if not flags:
                st.write("✅ No major issues found.")
            else:
                for flag in flags:
                    st.warning(f"{flag}")

        with c2:
            st.subheader("✅ Verified Facts")
            facts = final_data.get("verified_facts", [])
            if not facts:
                st.write("⚠️ No facts could be independently verified.")
            else:
                for fact in facts:
                    st.success(f"{fact}")
