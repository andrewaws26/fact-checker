import streamlit as st
from tavily import TavilyClient
import json
import re

# --- 1. Page Configuration ---
st.set_page_config(page_title="NewsGrader Pro", page_icon="⚖️", layout="wide")

# --- 2. Custom CSS ---
st.markdown("""
    <style>
    .letter-grade { font-size: 80px; font-weight: 800; text-align: center; line-height: 1; margin-bottom: 10px; }
    .metric-card { background-color: #f8f9fa; border: 1px solid #e9ecef; border-radius: 10px; padding: 20px; height: 100%; text-align: center; }
    .verdict-box { background-color: #eef2f5; border-left: 5px solid #3498db; padding: 15px; border-radius: 5px; font-size: 18px; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. Helper: JSON Cleaner ---
def clean_and_parse_json(raw_text):
    if not raw_text: return None
    text = str(raw_text)
    # Extract JSON from markdown code blocks if present
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if match: text = match.group(1)
    try:
        return json.loads(text)
    except:
        return None

# --- 4. Main UI ---
st.title("⚖️ NewsGrader Pro")
st.caption("AI-Powered Truth & Accuracy Auditor (Live Streaming)")

with st.sidebar:
    st.title("⚙️ Settings")
    default_key = st.secrets.get("TAVILY_API_KEY", "")
    api_key = st.text_input("Tavily API Key", value=default_key, type="password")
    st.divider()
    model = "mini" if st.radio("Depth:", ["Mini", "Pro"]) == "Mini" else "pro"

# Using st.form ensures stability
with st.form("audit"):
    url = st.text_input("Article URL", placeholder="https://example.com/...")
    run_btn = st.form_submit_button("Run Audit")

if run_btn:
    if not api_key or not url:
        st.error("Please check your API Key and URL.")
        st.stop()
        
    client = TavilyClient(api_key=api_key.strip())
    
    # Define Strict Schema
    schema = {
        "properties": {
            "letter_grade": {"type": "string", "enum": ["A","B","C","D","F"], "description": "Grade (A-F) of accuracy."},
            "one_sentence_verdict": {"type": "string", "description": "Concise summary."},
            "red_flags": {"type": "array", "items": {"type": "string"}, "description": "List of errors/lies."},
            "verified_facts": {"type": "array", "items": {"type": "string"}, "description": "List of true claims."},
            "sources_used": {"type": "array", "items": {"type": "string"}, "description": "List of sources."}
        },
        "required": ["letter_grade", "one_sentence_verdict", "red_flags", "verified_facts"]
    }

    # --- ROBUST STREAMING LOGIC ---
    full_json = ""
    
    with st.status("🚀 Connecting to Agent...", expanded=True) as status:
        try:
            stream = client.research(
                input=f"Fact-check this: {url}",
                model=model,
                output_schema=schema,
                stream=True
            )
            
            # Buffer for partial chunks
            buffer = ""
            
            for chunk in stream:
                # 1. Decode bytes to string
                text_chunk = chunk.decode("utf-8") if isinstance(chunk, bytes) else str(chunk)
                buffer += text_chunk
                
                # 2. Process complete lines only
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    
                    if line.startswith("data:"):
                        try:
                            # Parse the inner JSON data
                            data_str = line[5:].strip() # Remove "data:" prefix
                            data = json.loads(data_str)
                            
                            # Handle Content (Building the Report)
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            if "content" in delta:
                                full_json += delta["content"]
                                
                            # Handle Status Updates (Logs)
                            if "step_details" in delta:
                                step = delta["step_details"]
                                msg = step.get("step", "")
                                if msg: status.write(f"⚡ {msg}")
                        except:
                            continue
            
            status.update(label="Audit Complete!", state="complete", expanded=False)
            
        except Exception as e:
            st.error(f"Stream Error: {e}")
            st.stop()

    # --- Display Results ---
    final_data = clean_and_parse_json(full_json)
    
    if final_data:
        # Define Colors
        colors = {"A": "#2ecc71", "B": "#3498db", "C": "#f1c40f", "D": "#e67e22", "F": "#e74c3c"}
        grade = final_data.get("letter_grade", "C")
        
        st.divider()
        c1, c2 = st.columns([1, 4])
        with c1:
            st.markdown(f"<div class='metric-card'><div class='letter-grade' style='color:{colors.get(grade, '#999')}'>{grade}</div></div>", unsafe_allow_html=True)
        with c2:
            st.markdown("### Verdict")
            st.info(final_data.get("one_sentence_verdict", "No verdict."))
            if "sources_used" in final_data:
                st.caption(f"📚 Sources: {', '.join(final_data['sources_used'][:3])}")

        st.divider()
        col_a, col_b = st.columns(2)
        with col_a:
            st.error("🛑 Red Flags")
            for x in final_data.get("red_flags", []): st.write(f"• {x}")
        with col_b:
            st.success("✅ Verified Facts")
            for x in final_data.get("verified_facts", []): st.write(f"• {x}")
            
    else:
        st.error("Parsing Failed. Raw Output below:")
        st.code(full_json)
