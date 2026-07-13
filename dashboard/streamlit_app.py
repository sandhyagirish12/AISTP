import os
import sys
import time
from io import BytesIO
from pathlib import Path

from PIL import Image
import requests
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import init_db, save_result, save_image_result, get_history, get_image_history
from app.safety import score_text as score_text_local
from app.safety import score_image_bytes as score_image_bytes_local
from app.safety import score_video_bytes as score_video_bytes_local


init_db()


def get_api_url() -> str:
    configured_url = os.getenv("API_URL", "").strip() or os.getenv("BACKEND_URL", "").strip()
    if configured_url:
        return configured_url.rstrip("/")
    return ""


API_URL = get_api_url()


def request_json(method: str, path: str, **kwargs):
    if not API_URL:
        return None, "No remote API configured; using built-in scoring fallback"

    url = f"{API_URL}{path}"
    try:
        response = requests.request(method, url, timeout=10, **kwargs)
    except requests.RequestException as exc:
        return None, f"Unable to reach backend: {exc}"

    if not response.ok:
        detail = response.text[:300].strip().replace("\n", " ")
        return None, f"Backend returned status {response.status_code}: {detail or 'no details'}"

    try:
        return response.json(), None
    except ValueError as exc:
        detail = response.text[:300].strip().replace("\n", " ")
        return None, f"Backend returned invalid JSON: {detail or str(exc)}"


def score_text_with_fallback(text: str):
    if API_URL:
        data, error = request_json("post", "/score", json={"text": text})
        if not error:
            return data, None
        st.caption(f"Remote backend unavailable; using built-in scoring fallback: {error}")

    data = score_text_local(text)
    save_result({
        "text": text,
        "toxicity": data["toxicity"],
        "bias": data["bias"],
        "disallowed": data["disallowed"],
        "overall_score": data["overall_score"],
        "label": data["label"],
    })
    return data, None


def score_image_with_fallback(uploaded_file_name: str, image_bytes: bytes):
    if API_URL:
        files = {"file": (uploaded_file_name, image_bytes, "application/octet-stream")}
        data, error = request_json("post", "/score-image", files=files)
        if not error:
            return data, None
        st.caption(f"Remote backend unavailable; using built-in scoring fallback: {error}")

    data = score_image_bytes_local(image_bytes)
    save_image_result({
        "filename": uploaded_file_name,
        "graphic": data["graphic"],
        "violence": data["violence"],
        "nsfw": data["nsfw"],
        "overall_score": data["overall_score"],
        "label": data["label"],
    })
    return data, None


def score_video_with_fallback(uploaded_video_name: str, video_bytes: bytes):
    if API_URL:
        files = {"file": (uploaded_video_name, video_bytes, "application/octet-stream")}
        data, error = request_json("post", "/score-video", files=files)
        if not error:
            return data, None
        st.caption(f"Remote backend unavailable; using built-in scoring fallback: {error}")

    data = score_video_bytes_local(video_bytes)
    return data, None


def history_with_fallback(path: str):
    if API_URL:
        data, error = request_json("get", path)
        if not error:
            return data
        st.caption(f"Remote backend unavailable; using local history fallback: {error}")

    if path == "/history":
        return get_history()
    if path == "/history-images":
        return get_image_history()
    return []


def main() -> None:
    st.set_page_config(page_title="AI Safety Toolkit", layout="wide")
    st.title("AI Safety Toolkit for Open-Weight Model Outputs")

    st.markdown(
        """
        <style>
        div.stButton > button {
            background-color: #0072ff;
            color: white;
            font-size: 1.1rem;
            font-weight: 700;
            padding: 0.85rem 1.6rem;
            border-radius: 12px;
            border: none;
            box-shadow: 0 6px 16px rgba(0, 114, 255, 0.25);
        }
        div.stButton > button:hover {
            background-color: #005ad1;
        }
        div.stButton > button:focus {
            outline: 2px solid #bfdcff;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    instruction_style = "border:1px solid #d3d3d3; border-radius:10px; padding:16px; background-color:#f4f4f4; color:#333;"

    tabs = st.tabs(["Text Safety", "Image Safety", "Video Safety"])

    with tabs[0]:
        st.subheader("Text safety assessment")
        st.markdown(
            f'<div style="{instruction_style}">' 
            '<strong>Instructions</strong><br>'
            'Paste or type model-generated text below, then click Score. '
            'The dashboard returns toxicity, bias, disallowed content risk scores, '
            'and an overall safety label.'
            '</div>',
            unsafe_allow_html=True,
        )
        # show last text result if present
        if st.session_state.get("last_text_result"):
            last = st.session_state["last_text_result"]
            st.markdown("**Last text result**")
            st.metric("Overall label", last.get("label", "unknown"))
            st.write(
                f"- Overall score: {last.get('overall_score', 0):.2f}\n"
                f"- Toxicity: {last.get('toxicity', 0):.2f}\n"
                f"- Bias: {last.get('bias', 0):.2f}\n"
                f"- Disallowed: {last.get('disallowed', 0):.2f}"
            )
            if last.get("explanation"):
                st.markdown("**Why:**  \n" + last.get("explanation").replace("\n", "  \n"))

        text_input = st.text_area("Model output text", height=220)
        if st.button("Score text"):
            if not text_input.strip():
                st.warning("Enter text to score.")
            else:
                with st.spinner("Calculating text risk score..."):
                    start = time.perf_counter()
                    data, error = score_text_with_fallback(text_input)
                    elapsed = time.perf_counter() - start

                if error:
                    st.error(f"Failed to score text: {error}")
                else:
                    # persist until next score or reload
                    st.session_state["last_text_result"] = data
                    label = data.get("label", "unknown")
                    st.metric("Overall label", label)
                    st.write("### Risk details")
                    st.write(
                        f"- Toxicity: {data['toxicity']:.2f}\n"
                        f"- Bias: {data['bias']:.2f}\n"
                        f"- Disallowed content: {data['disallowed']:.2f}\n"
                        f"- Overall score: {data['overall_score']:.2f}"
                    )
                    st.caption(f"Estimated calculation time: {elapsed:.2f} seconds")
                    if data.get("explanation"):
                        st.markdown("**Why:**  \n" + data.get("explanation").replace("\n", "  \n"))

        st.write("### Recent text scoring history")
        history = history_with_fallback("/history")
        if history:
            for item in history:
                st.markdown(
                    f"**{item['label'].upper()}** — {item['created_at']}  \n"
                    f"Text: {item['text']}  \n"
                    f"Scores: toxicity={item['toxicity']:.2f}, bias={item['bias']:.2f}, disallowed={item['disallowed']:.2f}, overall={item['overall_score']:.2f}"
                )
                st.markdown("---")
        else:
            st.info("No text scoring history yet.")

    with tabs[1]:
        st.subheader("Image safety assessment")
        st.markdown(
            f'<div style="{instruction_style}">' 
            '<strong>Instructions</strong><br>'
            'Upload an AI-generated image below, then click Score image. '
            'The dashboard estimates graphic, violence, and NSFW risk scores.'
            '</div>',
            unsafe_allow_html=True,
        )
        uploaded_file = st.file_uploader(
            "Upload AI-generated image",
            type=["png", "jpg", "jpeg", "gif", "bmp"],
        )
        # if a new file is selected, clear stored image result for a different filename
        if uploaded_file is not None and st.session_state.get("last_image_result") and st.session_state["last_image_result"].get("filename") != uploaded_file.name:
            del st.session_state["last_image_result"]

        # show last image result if present
        if st.session_state.get("last_image_result"):
            last = st.session_state["last_image_result"]
            st.markdown("**Last image result**")
            st.metric("Image label", last.get("label", "unknown"))
            st.write(
                f"- Overall score: {last.get('overall_score', 0):.2f}\n"
                f"- Graphic: {last.get('graphic', 0):.2f}\n"
                f"- Violence: {last.get('violence', 0):.2f}\n"
                f"- NSFW: {last.get('nsfw', 0):.2f}"
            )
            if last.get("explanation"):
                st.markdown("**Why:**  \n" + last.get("explanation").replace("\n", "  \n"))

        if uploaded_file is not None:
            image_bytes = uploaded_file.read()
            image = Image.open(BytesIO(image_bytes))
            width, height = image.size
            file_size_mb = len(image_bytes) / (1024 * 1024)

            col1, col2 = st.columns([1, 2])
            with col1:
                st.image(image, caption="Thumbnail preview", width=240)
            with col2:
                st.write(f"- Filename: {uploaded_file.name}")
                st.write(f"- Dimensions: {width} x {height}")
                st.write(f"- File size: {file_size_mb:.2f} MB")
                st.write(f"- Format: {image.format}")

            if st.button("Score image"):
                with st.spinner("Calculating image risk score..."):
                    start = time.perf_counter()
                    data, error = score_image_with_fallback(uploaded_file.name, image_bytes)
                    elapsed = time.perf_counter() - start

                if error:
                    st.error(f"Failed to score image: {error}")
                else:
                    # persist until next upload or reload
                    data_store = data.copy()
                    data_store["filename"] = uploaded_file.name
                    st.session_state["last_image_result"] = data_store
                    st.metric("Image label", data.get("label", "unknown"))
                    st.write("### Image risk details")
                    st.write(
                        f"- Graphic sensitivity: {data['graphic']:.2f}\n"
                        f"- Violence risk: {data['violence']:.2f}\n"
                        f"- NSFW risk: {data['nsfw']:.2f}\n"
                        f"- Overall score: {data['overall_score']:.2f}"
                    )
                    st.caption(f"Estimated calculation time: {elapsed:.2f} seconds")
                    if data.get("explanation"):
                        st.markdown("**Why:**  \n" + data.get("explanation").replace("\n", "  \n"))

        st.write("### Recent image scoring history")
        history_img = history_with_fallback("/history-images")
        if history_img:
            for item in history_img:
                st.markdown(
                    f"**{item['label'].upper()}** — {item['created_at']}  \n"
                    f"Image: {item['filename']}  \n"
                    f"Scores: graphic={item['graphic']:.2f}, violence={item['violence']:.2f}, nsfw={item['nsfw']:.2f}, overall={item['overall_score']:.2f}"
                )
                st.markdown("---")
        else:
            st.info("No image scoring history yet.")

    with tabs[2]:
        st.subheader("Video safety assessment")
        st.markdown(
            f'<div style="{instruction_style}">' 
            '<strong>Instructions</strong><br>'
            'Upload a short video clip below, then click Score video. '
            'The dashboard estimates graphic, violence, and NSFW risk scores from a sampled frame and clip length.'
            '</div>',
            unsafe_allow_html=True,
        )
        uploaded_video = st.file_uploader(
            "Upload a video clip",
            type=["mp4", "mov", "avi", "mkv", "webm"],
        )
        # clear previous video result when a new file is selected
        if uploaded_video is not None and st.session_state.get("last_video_result") and st.session_state["last_video_result"].get("filename") != uploaded_video.name:
            del st.session_state["last_video_result"]

        # show last video result if present
        if st.session_state.get("last_video_result"):
            last = st.session_state["last_video_result"]
            st.markdown("**Last video result**")
            st.metric("Video label", last.get("label", "unknown"))
            st.write(
                f"- Overall score: {last.get('overall_score', 0):.2f}\n"
                f"- Graphic: {last.get('graphic', 0):.2f}\n"
                f"- Violence: {last.get('violence', 0):.2f}\n"
                f"- NSFW: {last.get('nsfw', 0):.2f}"
            )
            if last.get("explanation"):
                st.markdown("**Why:**  \n" + last.get("explanation").replace("\n", "  \n"))

        if uploaded_video is not None:
            st.write(f"- Filename: {uploaded_video.name}")
            st.write(f"- File size: {len(uploaded_video.getvalue()) / (1024 * 1024):.2f} MB")
            if st.button("Score video"):
                with st.spinner("Calculating video risk score..."):
                    start = time.perf_counter()
                    data, error = score_video_with_fallback(uploaded_video.name, uploaded_video.getvalue())
                    elapsed = time.perf_counter() - start

                if error:
                    st.error(f"Failed to score video: {error}")
                else:
                    # persist until next upload or reload
                    data_store = data.copy()
                    data_store["filename"] = uploaded_video.name
                    st.session_state["last_video_result"] = data_store
                    st.metric("Video label", data.get("label", "unknown"))
                    st.write("### Video risk details")
                    st.write(
                        f"- Graphic sensitivity: {data['graphic']:.2f}\n"
                        f"- Violence risk: {data['violence']:.2f}\n"
                        f"- NSFW risk: {data['nsfw']:.2f}\n"
                        f"- Overall score: {data['overall_score']:.2f}"
                    )
                    st.caption(f"Estimated calculation time: {elapsed:.2f} seconds")
                    if data.get("explanation"):
                        st.markdown("**Why:**  \n" + data.get("explanation").replace("\n", "  \n"))


if __name__ == "__main__":
    main()
