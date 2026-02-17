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
def parse_final_json(raw_data):
    if isinstance(raw_data, dict): return raw_data
    if not raw_data: return None
    text = str(raw_data)
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

with st.form("audit"):
    url = st.text_input("Article URL", placeholder="https://example.com/...")
    run_btn = st.form_submit_button("Run Audit")

if run_btn:
    if not api_key or not url:
        st.error("Please check your API Key and URL.")
        st.stop()
    
    # Clean Key
    safe_key = str(api_key).strip()
    try: safe_key = safe_key.encode("ascii", "ignore").decode("ascii")
    except: pass
        
    client = TavilyClient(api_key=safe_key)
    
    # Strict Schema
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
    full_report_text = ""
    final_json_obj = None
    debug_log = []
    
    with st.status("🚀 Connecting to Agent...", expanded=True) as status:
        try:
            response = client.research(
                input=f"Fact-check this: {url}",
                model=model,
                output_schema=schema,
                stream=True
            )
            
            # --- THE BUFFER PROCESSOR ---
            # This logic fixes the "Extra Data" error by handling split packets
            buffer = ""
            
            for chunk in response:
                # 1. Decode Chunk
                text_chunk = chunk.decode("utf-8") if isinstance(chunk, bytes) else str(chunk)
                buffer += text_chunk
                
                # 2. Process COMPLETE lines only
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    
                    # Skip empty lines or keep-alives
                    if not line or not line.startswith("data:"):
                        continue
                        
                    # 3. Parse JSON from the line
                    try:
                        raw_payload = line[5:].strip() # Remove "data:" prefix
                        if raw_payload == "[DONE]": break
                        
                        data = json.loads(raw_payload)
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        
                        # --- Handle Status (Thinking/Planning) ---
                        if "step_details" in delta:
                            step = delta["step_details"]
                            step_type = step.get("type", "")
                            if step_type == "research_plan":
                                status.write(f"📋 **Plan:** {step.get('step', 'Planning...')}")
                            elif step_type == "research":
                                status.write(f"🔍 **Researching:** {step.get('step', 'Searching...')}")
                            elif step_type == "think":
                                status.write("💭 **Thinking...**")

                        # --- Handle Content (The Result) ---
                        if "content" in delta:
                            content = delta["content"]
                            if isinstance(content, dict):
                                final_json_obj = content
                                status.write("⚡ Receiving structured data...")
                            else:
                                full_report_text += str(content)
                                
                    except Exception as e:
                        # Log parsing errors but don't kill the stream
                        debug_log.append(f"Line Parse Error: {e}")
                        continue

            status.update(label="Audit Complete!", state="complete", expanded=False)
            
        except Exception as e:
            st.error(f"Stream Connection Error: {e}")
            st.stop()

    # --- RESULT PARSING ---
    if final_json_obj:
        final_data = final_json_obj
    elif full_report_text:
        final_data = parse_final_json(full_report_text)
    else:
        final_data = None

    # --- DISPLAY ---
    if final_data:
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
        st.error("Parsing Failed.")
        with st.expander("🕵️ Debug Logs"):
            st.write(debug_log)
            st.text_area("Accumulated Text:", full_report_text)
            st.write("Final Object:", final_json_obj)
