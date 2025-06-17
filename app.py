import chainlit as cl
import requests
import base64
import json
import uuid
import os
import logging
from io import BytesIO
try:
    from PIL import Image
except ImportError:
    Image = None

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')

# # TEST URL for n8n webhook
# WEBHOOK_URL = "https://togn8n.cloudnavision.com/webhook-test/0ebad23d-6a5a-441e-b0de-b4ce724a84ce"

# Production URL for n8n webhook
WEBHOOK_URL = "https://togn8n.cloudnavision.com/webhook/0ebad23d-6a5a-441e-b0de-b4ce724a84ce"

# Allowed file types and max size (e.g., 10MB)
ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "application/pdf"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

@cl.on_chat_start
async def start():
    cl.user_session.set("session_id", None)
    cl.user_session.set("user_name", None)
    cl.user_session.set("user_data", None)
    session_id = str(uuid.uuid4())
    cl.user_session.set("session_id", session_id)

    # Use Markdown for welcome message with no heading underline
    await cl.Message(
        content=(
            "## 👋 Welcome to EverTrustLanka Bank!\n"
            ">📁 Drop files here or use the attachment button\n"
            ">🤖 I'm your AI-powered banking assistant, here to help you 24/7. If I make a mistake, please point out the mistake and the correct way, so I can learn and improve.\n\n"
            "How can I assist you today?\n"
            "You can ask me about our services, or even start a loan application.\n"
        )
    ).send()

@cl.on_message
async def main(message: cl.Message):
    user_text = message.content or ""
    files_data = []
    uploaded_names = []

    # Check if there are files uploaded
    has_files = message.elements and len(message.elements) > 0
    has_text = user_text.strip() != ""
    
    # If files are uploaded without text, treat it as file processing request
    if has_files and not has_text:
        user_text = "File uploaded for processing"
    
    # Skip processing if no files and no text (empty message)
    if not has_files and not has_text:
        await cl.Message("Please upload a file or send a message.").send()
        return

    if message.elements:
        logging.info(f"message.elements = {message.elements}")
        for element in message.elements:
            # Handle both File and Image elements
            if isinstance(element, (cl.File, cl.Image)):
                logging.info(f"Processing element '{element.name}' with MIME type '{element.mime}' and type '{type(element).__name__}'")
                uploaded_names.append(element.name)
                file_content = element.content

                # Attempt to read file content from its path if content is None
                if file_content is None and hasattr(element, "path") and element.path:
                    logging.info(f"Attempting to read file from path '{element.path}'")
                    if not os.path.exists(element.path):
                        await cl.Message(f"❌ File path '{element.path}' does not exist.").send()
                        logging.warning(f"File path '{element.path}' does not exist.")
                        continue
                    if not os.access(element.path, os.R_OK):
                        await cl.Message(f"❌ File path '{element.path}' is not readable.").send()
                        logging.warning(f"File path '{element.path}' is not readable.")
                        continue
                    try:
                        with open(element.path, "rb") as file:
                            file_content = file.read()
                        logging.info(f"Successfully read content from path '{element.path}'")
                    except Exception as e:
                        await cl.Message(f"❌ Failed to read file '{element.name}' from path: {str(e)}").send()
                        logging.error(f"Failed to read file '{element.name}' from path: {str(e)}")
                        continue

                # File type validation
                if element.mime not in ALLOWED_MIME_TYPES:
                    await cl.Message(f"❌ File '{element.name}' type '{element.mime}' is not allowed.").send()
                    logging.warning(f"File '{element.name}' type '{element.mime}' is not allowed.")
                    continue

                # Convert PDF to PNG if needed
                if element.mime == "application/pdf":
                    try:
                        from pdf2image import convert_from_bytes
                    except ImportError:
                        await cl.Message(f"❌ pdf2image is required to convert PDF to PNG. Please install it.").send()
                        logging.error("pdf2image is not installed.")
                        continue
                    try:
                        images = convert_from_bytes(file_content, first_page=1, last_page=1)
                        if not images:
                            raise Exception("No images generated from PDF.")
                        png_buffer = BytesIO()
                        images[0].save(png_buffer, format="PNG")
                        file_content = png_buffer.getvalue()
                        element.mime = "image/png"
                        # Change file extension to .png
                        if element.name.lower().endswith('.pdf'):
                            element.name = element.name.rsplit('.', 1)[0] + '.png'
                        logging.info(f"Converted PDF '{element.name}' to PNG.")
                    except Exception as e:
                        await cl.Message(f"❌ Failed to convert PDF to PNG for '{element.name}': {str(e)}").send()
                        logging.error(f"Failed to convert PDF to PNG for '{element.name}': {str(e)}")
                        continue

                # Convert JPEG to PNG if needed
                if element.mime == "image/jpeg":
                    if Image is None:
                        await cl.Message(f"❌ Pillow (PIL) is required to convert JPEG to PNG. Please install it.").send()
                        logging.error("Pillow (PIL) is not installed.")
                        continue
                    try:
                        img = Image.open(BytesIO(file_content))
                        png_buffer = BytesIO()
                        img.save(png_buffer, format="PNG")
                        file_content = png_buffer.getvalue()
                        element.mime = "image/png"
                        # Change file extension to .png
                        if element.name.lower().endswith('.jpg') or element.name.lower().endswith('.jpeg'):
                            element.name = element.name.rsplit('.', 1)[0] + '.png'
                        logging.info(f"Converted JPEG '{element.name}' to PNG.")
                    except Exception as e:
                        await cl.Message(f"❌ Failed to convert JPEG to PNG for '{element.name}': {str(e)}").send()
                        logging.error(f"Failed to convert JPEG to PNG for '{element.name}': {str(e)}")
                        continue

                if file_content is None:
                    await cl.Message(f"❌ File '{element.name}' has no content after all attempts.").send()
                    logging.warning(f"File '{element.name}' has no content after all attempts.")
                    continue
                elif isinstance(file_content, str):
                    file_content = file_content.encode("utf-8")

                # File size validation
                if len(file_content) > MAX_FILE_SIZE:
                    await cl.Message(f"❌ File '{element.name}' exceeds the maximum allowed size of 10MB.").send()
                    logging.warning(f"File '{element.name}' exceeds size limit.")
                    continue

                try:
                    base64_content = base64.b64encode(file_content).decode("utf-8")
                    files_data.append({
                        "name": element.name,
                        "type": element.mime,
                        "content_base64": base64_content
                    })
                    logging.info(f"Successfully processed element '{element.name}'")
                except Exception as e:
                    await cl.Message(f"❌ Failed to process file '{element.name}': {str(e)}").send()
                    logging.error(f"Failed to process file '{element.name}': {str(e)}")
                    continue

        if not files_data:
            logging.info("No files_data generated")
    else:
        logging.info("No elements in message.elements")

    session_id = cl.user_session.get("session_id")

    # Prepare a safe-to-log payload (no base64 content)
    log_payload = {
        "session_id": session_id,
        "text": user_text,
        "files": [
            {"name": f["name"], "type": f["type"]} for f in files_data
        ]
    }
    logging.info("Payload being sent: %s", json.dumps(log_payload, indent=2))

    payload = {
        "session_id": session_id,
        "text": user_text,
        "files": files_data
    }
    # Remove logging of the full payload to avoid large base64 output
    # logging.info("Payload being sent: %s", json.dumps(payload, indent=2))
    
    try:
        response = requests.post(WEBHOOK_URL, json=payload)
        response.raise_for_status()

        try:
            resp = response.json()
            if isinstance(resp, dict):
                if "output" in resp:
                    resp_pretty = resp["output"]
                elif "message" in resp:
                    resp_pretty = resp["message"]
                else:
                    resp_pretty = json.dumps(resp, indent=2)
            else:
                resp_pretty = json.dumps(resp, indent=2)
        except ValueError:
            resp_pretty = response.text

        msg = ""
        if uploaded_names:
            msg += "**Uploaded files:** " + ", ".join(uploaded_names) + "\n"
        msg += resp_pretty

        await cl.Message(msg).send()

    except Exception as e:
        await cl.Message(f"❌ Failed to send data to n8n: {str(e)}").send()