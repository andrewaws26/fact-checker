import streamlit as st
from tavily import TavilyClient
import json
import re

# --- 1. Page Configuration ---
st.set_page_config(
    page_title="NewsGrader Pro", 
    page_icon="⚖️", 
    layout="wide"
)

# --- 2. Custom CSS ---
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
        text-align: center;
    }
    .verdict-box {
        background-color: #eef2f5;
        border-left: 5px solid #3498db;
        padding: 15px;
        border-radius: 5px;
        font-size: 18px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. Helper: Robust JSON Parser ---
def clean_and_parse_json(raw_text):
    """
    Cleans accumulated stream text (stripping markdown) and parses JSON.
    """
    if not raw_text: 
        return None
        
    text = str(raw_text)
    # 1. Try to find JSON inside markdown code blocks
    pattern = r"```json\s*(.*?)\s*```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        text = match.group(1)
        
    # 2. Attempt Parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None

# --- 4. Main UI Logic ---
st.title("⚖️ NewsGrader Pro")
st.caption("AI-Powered Truth & Accuracy Auditor (Live Streaming)")

# Sidebar
with st.sidebar:
    st.title("⚙️ Settings")
    default_key = st.secrets.get("TAVILY_API_KEY", "")
    api_key = st.text_input("Tavily API Key", value=default_key, type="password")
    
    st.divider()
    research_mode = st.radio("Depth:", ["Mini (Fast)", "Pro (Deep Audit)"], index=0)
    selected_model = "mini" if "Mini" in research_mode else "pro"

# Form
with st.form("audit_form"):
    url_input = st.text_input("Article URL", placeholder="https://www.nytimes.com/...")
    submitted = st.form_submit_button("Run Audit")

if submitted:
    if not api_key:
        st.error("⚠️ Please provide a Tavily API Key.")
        st.stop()
    if not url_input:
        st.error("⚠️ Please provide a URL.")
        st.stop()

    # Clean API Key
    clean_key = str(api_key).strip()
    try: clean_key = clean_key.encode("ascii", "ignore").decode("ascii")
    except: pass
    
    client = TavilyClient(api_key=clean_key)

    # --- Schema Definition ---
    audit_schema = {
        "properties": {
            "letter_grade": {"type": "string", "enum": ["A", "B", "C", "D", "F"], "description": "Overall accuracy grade (A-F)."},
            "one_sentence_verdict": {"type": "string", "description": "Concise summary of findings."},
            "red_flags": {"type": "array", "items": {"type": "string"}, "description": "List of inaccuracies or missing context."},
            "verified_facts": {"type": "array", "items": {"type": "string"}, "description": "List of verified true claims."},
            "sources_used": {"type": "array", "items": {"type": "string"}, "description": "List of authoritative sources used."}
        },
        "required": ["letter_grade", "one_sentence_verdict", "red_flags", "verified_facts"]
    }

    prompt = f"Act as a strict Fact-Checker. Audit this article: {url_input}. Cross-Reference claims against external sources."

    # --- STREAMING LOGIC START ---
    
    full_json_buffer = "" # We will build the final JSON string here
    final_data = None
    
    # Create a Status Container to show live updates
    with st.status("🚀 Connecting to Research Agent...", expanded=True) as status:
        
        try:
            # Call API with stream=True
            response_stream = client.research(
                input=prompt,
                model=selected_model,
                output_schema=audit_schema,
                stream=True
            )
            
            # Variables to track stream state
            current_event_type = None
            last_step_msg = ""
            
            # Iterate through the stream chunks
            for chunk in response_stream:
                # Decode bytes to string if needed
                line = chunk.decode("utf-8").strip() if isinstance(chunk, bytes) else str(chunk).strip()
                if not line: continue

                # Manual SSE (Server-Sent Events) Parsing
                # The Tavily API sends "event: ..." followed by "data: ..."
                
                if line.startswith("event:"):
                    current_event_type = line.split("event:", 1)[1].strip()
                    
                elif line.startswith("data:"):
                    # Parse the JSON data payload inside the SSE line
                    try:
                        data_str = line.split("data:", 1)[1].strip()
                        data = json.loads(data_str)
                    except:
                        continue # Skip malformed lines

                    # A. Handle Final Content (The Report/JSON)
                    if current_event_type == "chat.completion.chunk":
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        if "content" in delta:
                            content_chunk = delta["content"]
                            full_json_buffer += content_chunk
                            # Optionally show raw JSON building up (can be noisy)
                            # status.markdown(f"Writing report... {len(full_json_buffer)} chars")

                    # B. Handle Research Steps (The "What is it doing?" part)
                    elif "step_details" in delta:
                        step = delta["step_details"]
                        step_type = step.get("type")
                        
                        # 1. Plan
                        if step_type == "research_plan":
                            plan = step.get("step", "Planning...")
                            status.write(f"📋 **Plan:** {plan}")
                            
                        # 2. Research (Searching)
                        elif step_type == "research":
                            msg = step.get("step", "")
                            if msg != last_step_msg: # Avoid duplicates
                                status.write(f"🔍 **Searching:** {msg}")
                                last_step_msg = msg
                                
                        # 3. Thinking
                        elif step_type == "think":
                            status.write(f"💭 **Thinking:** {step.get('step', '')}")

                    # C. Handle Tool Calls (Specific URLs being visited)
                    elif "tool_calls" in delta:
                        # Sometimes tool calls appear here depending on API version
                        pass

            # Loop finished
            status.update(label="Audit Complete!", state="complete", expanded=False)
            
        except Exception as e:
            st.error(f"Stream Error: {str(e)}")
            st.stop()

    # --- STREAMING LOGIC END ---

    # Parse the accumulated JSON
    if full_json_buffer:
        final_data = clean_and_parse_json(full_json_buffer)
    
    # --- 5. Display Results (Same as before) ---
    if final_data:
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
            st.markdown(f"<div class='verdict-box'>{final_data.get('one_sentence_verdict', 'No verdict provided.')}</div>", unsafe_allow_html=True)
            
            sources = final_data.get("sources_used", [])
            if sources:
                st.caption(f"📚 **Verified against:** {', '.join(sources[:3])}...")

        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("🛑 Red Flags")
            flags = final_data.get("red_flags", [])
            if not flags: st.success("✅ No major issues.")
            else:
                for flag in flags: st.warning(f"• {flag}")

        with c2:
            st.subheader("✅ Verified Facts")
            facts = final_data.get("verified_facts", [])
            if not facts: st.write("⚠️ No verifiable facts found.")
            else:
                for fact in facts: st.success(f"• {fact}")
    else:
        st.error("Failed to parse the final report.")
        with st.expander("Debug Raw Output"):
            st.code(full_json_buffer)
