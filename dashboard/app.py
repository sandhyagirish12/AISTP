import streamlit as st
import requests

API_URL = "http://localhost:8000"

st.set_page_config(page_title="AI Safety Toolkit", layout="wide")
st.title("AI Safety Toolkit for Open-Weight Model Outputs")

with st.sidebar:
    st.header("Instructions")
    st.write(
        "Paste or type model-generated text below, then click Score. "
        "The dashboard shows toxicity, bias, disallowed content risk scores, "
        "an overall label, and a history of scored outputs."
    )

text_input = st.text_area("Model output text", height=200)
if st.button("Score text"):
    if not text_input.strip():
        st.warning("Enter text to score.")
    else:
        response = requests.post(f"{API_URL}/score", json={"text": text_input})
        if response.status_code == 200:
            data = response.json()
            label = data.get("label", "unknown")
            st.metric("Overall label", label)
            st.write("### Risk details")
            st.write(
                f"- Toxicity: {data['toxicity']:.2f}\n"
                f"- Bias: {data['bias']:.2f}\n"
                f"- Disallowed content: {data['disallowed']:.2f}\n"
                f"- Overall score: {data['overall_score']:.2f}"
            )
        else:
            st.error("Failed to score text. Is the backend running?")

st.write("## Scoring history")
history_resp = requests.get(f"{API_URL}/history")
if history_resp.status_code == 200:
    history = history_resp.json()
    if history:
        for item in history:
            st.markdown(
                f"**{item['label'].upper()}** — {item['created_at']}  \n"
                f"Text: {item['text']}  \n"
                f"Scores: toxicity={item['toxicity']:.2f}, bias={item['bias']:.2f}, disallowed={item['disallowed']:.2f}, overall={item['overall_score']:.2f}"
            )
            st.markdown("---")
    else:
        st.info("No scoring history yet.")
else:
    st.error("Could not load history from backend.")
