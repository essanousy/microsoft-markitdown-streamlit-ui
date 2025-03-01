"""
Document Analyzer with Microsoft MarkItDown and LLM-based Image Description

This Streamlit application allows users to upload documents (including PDFs) and have their 
contents extracted, analyzed, and optionally enhanced by a Large Language Model (LLM). 
If enabled, embedded images in PDF pages can be individually extracted and described by 
the LLM, integrating figure references seamlessly into the extracted text.

Features:
- Supports various file formats: PDF, PPTX, DOCX, XLSX, images, audio, HTML, CSV, JSON, XML
- Extracts text content from uploaded documents via MarkItDown
- Integrates with both local LLMs (via a custom LocalLLMClient) and the OpenAI API (e.g., GPT-4)
- If LLM is enabled and the document is a PDF, it:
  - Uses pdfplumber to extract text and image positions from pages
  - Extracts and describes embedded images individually
  - Inserts figure references and LLM-generated captions inline with the extracted text

Installation and Requirements:
1. Python 3.8 or newer is recommended.
2. Install Streamlit:
   ```bash
   pip install streamlit
"""

import streamlit as st
import os
from markitdown import MarkItDown
from pathlib import Path
import tempfile
from dotenv import load_dotenv
import requests
from types import SimpleNamespace
import pdfplumber
from PIL import Image
import base64

# Attempt to import OpenAI; if not available, set OpenAI = None
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# Load environment variables
load_dotenv()

debug_logs = []
def log_debug(message: str):
    debug_logs.append(message)

class LocalLLMClient:
    def __init__(self, base_url="http://127.0.0.1:1234/v1/chat/completions"):
        self.base_url = base_url
        self.chat = self.Chat(self.base_url)

    class Chat:
        def __init__(self, base_url):
            self.base_url = base_url
            self.completions = LocalLLMClient.Chat.Completions(self.base_url)

        class Completions:
            def __init__(self, base_url):
                self.base_url = base_url

            def create(self, model, messages, temperature=0.7, max_tokens=-1, stream=False):
                log_debug("Preparing to send request to local LLM...")
                payload_size = 0
                for m in messages:
                    if isinstance(m.get("content"), list):
                        for c in m["content"]:
                            if c.get("type") == "image_url" and "data:image" in c["image_url"]["url"]:
                                image_data = c["image_url"]["url"].split(",")[1]
                                payload_size = len(image_data)
                                if payload_size > 3_000_000:
                                    log_debug("Image is too large to process with LLM.")
                                    return self._convert_to_objects({
                                        "choices": [{
                                            "message": {
                                                "role": "assistant",
                                                "content": "Image too large to process."
                                            }
                                        }]
                                    })

                payload = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": stream
                }
                log_debug(f"Request Payload: {payload}")
                try:
                    response = requests.post(self.base_url, json=payload, timeout=60)
                    log_debug(f"Request sent to {self.base_url}. HTTP status: {response.status_code}")
                    if response.status_code != 200:
                        log_debug(f"Non-200 status code: {response.status_code}")
                    data = response.json()
                    log_debug(f"Response JSON from LLM: {data}")
                    return self._convert_to_objects(data)
                except requests.Timeout:
                    log_debug("LLM request timed out.")
                    return self._convert_to_objects({
                        "choices": [{
                            "message": {
                                "role": "assistant",
                                "content": "The LLM request timed out."
                            }
                        }]
                    })
                except Exception as e:
                    log_debug(f"Error making LLM request: {str(e)}")
                    raise e

            def _convert_to_objects(self, data):
                def dict_to_namespace(d):
                    if isinstance(d, dict):
                        for k, v in d.items():
                            d[k] = dict_to_namespace(v)
                        return SimpleNamespace(**d)
                    elif isinstance(d, list):
                        return [dict_to_namespace(x) for x in d]
                    else:
                        return d
                return dict_to_namespace(data)

def clear_cache():
    if os.path.exists(".cache"):
        for file in os.listdir(".cache"):
            os.remove(os.path.join(".cache", file))
    st.cache_data.clear()
    log_debug("Cache cleared.")

def image_to_data_uri(pil_img):
    buffered = tempfile.TemporaryFile()
    pil_img.save(buffered, format="PNG")
    buffered.seek(0)
    img_str = base64.b64encode(buffered.read()).decode("utf-8")
    return f"data:image/png;base64,{img_str}"

def describe_image_with_llm(llm_client, llm_model, pil_img):
    with tempfile.TemporaryFile() as buffered:
        pil_img.save(buffered, format="PNG")
        buffered.seek(0)
        img_str = base64.b64encode(buffered.read()).decode("utf-8")
    
    data_uri = f"data:image/png;base64,{img_str}"

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe this image in detail:"},
                {
                    "type": "image_url",
                    "image_url": {"url": data_uri}
                }
            ]
        }
    ]
    response = llm_client.chat.completions.create(model=llm_model, messages=messages)
    return response.choices[0].message.content.strip()

def process_pdf_with_images_and_text(md, tmp_path, llm_client, llm_model):
    log_debug("Extracting text and images from PDF using pdfplumber.")
    text_pages = []
    figure_counter = 1

    with pdfplumber.open(tmp_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            # Extract text
            text = page.extract_text() or ""
            lines = text.split('\n')
            words = page.extract_words()

            # Approximate line positions
            line_positions = []
            for ln in lines:
                ln_words = [w for w in words if w['text'] in ln]
                if ln_words:
                    avg_y = sum(w['top'] for w in ln_words) / len(ln_words)
                else:
                    avg_y = None
                line_positions.append((ln, avg_y))

            # Extract images from the page
            # page.images returns a list of image dictionaries with keys: x0, y0, x1, y1
            figs = []
            page_img = page.to_image(resolution=150)
            pil_page_img = page_img.original  # Get the underlying PIL image

            for im in page.images:
                x0, y0, x1, y1 = im['x0'], im['y0'], im['x1'], im['y1']
                # Crop the PIL image at the bounding box of the image
                cropped = pil_page_img.crop((x0, y0, x1, y1))
                
                # Describe the image with LLM
                fig_desc = describe_image_with_llm(llm_client, llm_model, cropped)
                fig_y_mid = y0 + (y1 - y0) / 2.0
                figs.append((fig_y_mid, f"Figure {figure_counter}: {fig_desc}"))
                figure_counter += 1

            figs.sort(key=lambda f: f[0])

            # Integrate figures into text output
            output_lines = []
            fig_idx = 0
            for (ln, avg_y) in line_positions:
                output_lines.append(ln)
                while fig_idx < len(figs):
                    fig_y, fig_text = figs[fig_idx]
                    if avg_y is not None and fig_y >= avg_y:
                        output_lines.append(fig_text)
                        fig_idx += 1
                    else:
                        break

            # If any figures remain unmatched, place them at the end
            while fig_idx < len(figs):
                output_lines.append(figs[fig_idx][1])
                fig_idx += 1

            page_output = "\n".join(output_lines)
            text_pages.append(f"--- Page {page_num} ---\n{page_output}")

    return "\n\n".join(text_pages)

def process_document(uploaded_file, use_llm=False, llm_provider="Local", custom_api_key=None):


    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        tmp_path = tmp_file.name

    try:
        if use_llm:
            if llm_provider == "OpenAI":
                if OpenAI is None:
                    raise RuntimeError("OpenAI library not installed.")
                api_key = custom_api_key or os.getenv('OPENAI_API_KEY')
                if not api_key:
                    raise ValueError("OpenAI API key is required.")
                log_debug("Using OpenAI API client.")
                client = OpenAI(api_key=api_key)
                md = MarkItDown(llm_client=client, llm_model="gpt-4o")
                llm_client = client
                llm_model = "gpt-4o"
            else:
                log_debug("Using Local LLM client.")
                llm_client = LocalLLMClient()
                llm_model = "llama-3.1-unhinged-vision-8b"
                md = MarkItDown(llm_client=llm_client, llm_model=llm_model)
        else:
            log_debug("Not using LLM.")
            md = MarkItDown()
            llm_client = None
            llm_model = None

        extension = Path(uploaded_file.name).suffix.lower()
        # If PDF and LLM is enabled, do the image+text extraction via pdfplumber
        if extension == ".pdf" and use_llm:
            text_content = process_pdf_with_images_and_text(md, tmp_path, llm_client, llm_model)
        else:
            # Otherwise, just convert normally
            log_debug(f"Converting file with MarkItDown: {tmp_path}")
            result = md.convert(tmp_path)
            text_content = result.text_content.strip() if result and result.text_content else ""

        return text_content
    except Exception as e:
        log_debug(f"Error during document processing: {str(e)}")
        raise e
    finally:
        os.unlink(tmp_path)
        log_debug(f"Temporary file {tmp_path} removed.")

def main():
    st.set_page_config(
        page_title="Document Analyzer with Microsoft MarkItDown",
        page_icon="📄",
        layout="wide"
    )

    with st.sidebar:
        st.title("📄 Document Analyzer with Microsoft MarkItDown")
        st.write("Upload a PDF or other document to extract text and analyze embedded images using LLM.")
        
        uploaded_file = st.file_uploader(
            "Choose a file", 
            type=['pdf', 'pptx', 'docx', 'xlsx', 'jpg', 'png', 'mp3', 'wav', 'html', 'csv', 'json', 'xml']
        )

        st.header("LLM Provider")
        llm_provider = st.radio("Select LLM Provider", ["Local", "OpenAI"], index=0)

        st.header("Settings")
        use_llm = st.toggle("Use LLM for Enhanced Analysis", value=False)

        custom_api_key = None
        if use_llm and llm_provider == "OpenAI":
            st.info("OpenAI requires an API key for enhanced analysis")
            use_custom_key = st.checkbox("Use custom OpenAI API key")
            if use_custom_key:
                custom_api_key = st.text_input(
                    "Enter OpenAI API Key",
                    type="password",
                    help="Your API key will not be stored and is only used for this session"
                )

        if st.button("Clear Cache"):
            clear_cache()
            st.success("Cache cleared!")
        
        st.markdown("""
        ### Supported Formats:
        - PDF (Extract text + images and describe images inline if LLM enabled)
        - PPTX
        - DOCX
        - XLSX
        - Images
        - Audio
        - HTML
        - Text
        """)

    if uploaded_file:
        with st.spinner("Processing document..."):
            try:
                text_content = process_document(
                    uploaded_file, 
                    use_llm=use_llm, 
                    llm_provider=llm_provider, 
                    custom_api_key=custom_api_key
                )
                
                st.header("Analysis Results")
                tab1, tab2, tab3 = st.tabs(["Extracted Content", "Document Information", "Debug Logs"])
                
                with tab1:
                    st.text_area("Extracted Content", text_content, height=600)
                    st.download_button(
                        "Download Extracted Content",
                        text_content,
                        file_name=f"{uploaded_file.name}_extracted.md",
                        mime="text/plain"
                    )
                
                with tab2:
                    st.json({
                        "Filename": uploaded_file.name,
                        "File size (KB)": f"{uploaded_file.size / 1024:.2f}",
                        "File type": uploaded_file.type
                    })
                
                with tab3:
                    if debug_logs:
                        st.write("Debug Logs:")
                        for log in debug_logs:
                            st.write(log)
                    else:
                        st.write("No debug logs available.")
            except Exception as e:
                st.error(f"Error processing document: {str(e)}")
                if debug_logs:
                    st.write("Debug Logs:")
                    for log in debug_logs:
                        st.write(log)
    else:
        st.info("👈 Please upload a document using the sidebar to begin analysis")

if __name__ == "__main__":
    main()
