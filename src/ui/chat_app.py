import gradio as gr
import httpx

from src.utils.json_logging import logger_for, setup_json_logging

# API endpoint configuration
API_URL = "http://localhost:8000/chat"

# Initialize JSON logging for the UI process
setup_json_logging()
logger = logger_for("ui.chat")


async def send_message(message: str, file, history):
    """
    Send message to the FastAPI backend and return the response.
    """

    if not message.strip():
        return history

    # Add user message to chat history
    history.append({"role": "user", "content": message})

    logger.info(
        "ui_send_message",
        extra={"user_message": message, "file": file, "history": history},
    )

    # Convert history to List[str] format for the API
    conversation_history = [f"{msg['role']}: {msg['content']}" for msg in history]

    # Prepare the request payload
    payload = {
        "message": message,
        "file": None,
        "conversation_history": conversation_history,
    }

    # Handle file upload if present
    if file is not None:
        # For now, just note that a file was uploaded
        # We'll handle file processing later
        payload["file"] = str(file.name) if hasattr(file, "name") else str(file)

    try:
        # Call the FastAPI endpoint
        async with httpx.AsyncClient() as client:
            response = await client.post(API_URL, json=payload, timeout=30.0)
            response.raise_for_status()
            result = response.json()

            # Add assistant response to chat history
            history.append({"role": "assistant", "content": result["response"]})
            logger.info(
                "ui_received_response",
                extra={"response_preview": result.get("response")},
            )
    except Exception as e:
        # Handle errors gracefully
        history.append({"role": "assistant", "content": f"Error: {str(e)}"})
        logger.exception("ui_send_failed", extra={"error": str(e)})

    return history


def clear_chat():
    """
    Clear the chat history and start a new conversation.
    """
    return []


# Custom clean light theme
custom_theme = gr.themes.Soft(
    primary_hue="blue",
    secondary_hue="gray",
    neutral_hue="gray",
).set(
    body_background_fill="#ffffff",
    body_background_fill_dark="#ffffff",
    block_background_fill="#ffffff",
    block_background_fill_dark="#ffffff",
    block_border_width="1px",
    block_border_color="#e5e7eb",
    input_background_fill="#f9fafb",
    input_background_fill_dark="#f9fafb",
    button_primary_background_fill="#2563eb",
    button_primary_background_fill_hover="#1d4ed8",
    button_primary_text_color="#ffffff",
    button_secondary_background_fill="#f3f4f6",
    button_secondary_background_fill_hover="#e5e7eb",
    button_secondary_text_color="#374151",
)

# Create the Gradio interface with a clean light UI
with gr.Blocks(
    theme=custom_theme,
    css="""
        /* Global styles */
        .gradio-container {
            max-width: 100% !important;
            padding: 0 !important;
            margin: 0 !important;
            background: #ffffff !important;
        }
        
        /* Main container */
        .main-container {
            max-width: 920px;
            margin: 0 auto;
            padding: 1.5rem;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }
        
        /* Header */
        .header {
            text-align: center;
            padding: 1.5rem 0;
            border-bottom: 1px solid #e5e7eb;
            margin-bottom: 1.5rem;
        }
        
        .header h1 {
            color: #111827;
            font-size: 1.875rem;
            font-weight: 700;
            margin: 0;
        }
        
        .header p {
            color: #6b7280;
            font-size: 0.875rem;
            margin: 0.5rem 0 0 0;
        }
        
        /* New chat button container */
        .new-chat-container {
            margin-bottom: 1rem;
        }
        
        /* Chat container */
        .chat-wrapper {
            flex: 1;
            overflow-y: auto;
            overflow-x: hidden;
            margin-bottom: 0;
            background: #ffffff;
            border-radius: 12px;
            border: 0; /* cleaner, like ChatGPT */
            padding: 1rem;
            min-height: 0;
            height: auto !important;
            max-height: none !important;
        }
        
        /* Override Gradio's default height restrictions */
        .chat-wrapper > div {
            height: 100% !important;
            min-height: 650px !important;
        }
        
        /* Input area - sticky at bottom */
        .input-container {
            flex: 0 0 auto !important; /* do not stretch to fill leftover space */
            position: sticky;
            bottom: 0;
            background: #ffffff;
            border-radius: 12px;
            padding: 1rem;
            border: 1px solid #e5e7eb;
            box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.05);
            margin-top: 1rem;
            z-index: 10;
        }
        
        /* Textbox styling */
        .input-container textarea {
            background: #ffffff !important;
            border: 1px solid #d1d5db !important;
            border-radius: 8px !important;
            color: #111827 !important;
            font-size: 0.95rem !important;
            padding: 0.75rem !important;
            resize: none !important;
        }
        
        .input-container textarea:focus {
            border-color: #2563eb !important;
            outline: none !important;
            box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1) !important;
        }
        
        /* Button styling */
        button {
            border-radius: 8px !important;
            font-weight: 500 !important;
            padding: 0.625rem 1.25rem !important;
            transition: all 0.2s !important;
            border: 1px solid transparent !important;
        }
        
        /* File upload button - small and clean */
        .file-upload-btn {
            min-width: 40px !important;
            max-width: 40px !important;
            padding: 0 !important;
            margin: 0 !important;
            border: 0 !important;
        }
        
        .file-upload-btn button {
            width: 40px !important;
            height: 40px !important;
            padding: 0 !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            background: #f3f4f6 !important;
            border: 1px solid #d1d5db !important;
            color: #6b7280 !important;
        }
        
        .file-upload-btn button:hover {
            background: #e5e7eb !important;
            border-color: #9ca3af !important;
        }
        
        /* Hide long helper text inside upload */
        .file-upload-btn .wrap { 
            display: none !important; 
        }
        
        /* Hide floating label */
        .file-upload-btn label {
            display: none !important;
        }
        
        /* Chat messages */
        .message {
            padding: 10px 14px !important;
            border-radius: 10px !important;
            margin: 6px 0 !important;
            font-size: 0.95rem !important;
            line-height: 1.45 !important;
        }
        
        .message.user {
            background: #eff6ff !important;
            color: #1e40af !important;
        }
        
        .message.bot {
            background: #f9fafb !important;
            color: #111827 !important;
        }

        /* Make Chatbot bubbles compact (gradio 5) */
        .bubble-wrap * {
            font-size: 0.95rem !important;
            line-height: 1.45 !important;
        }
        .bubble-wrap [role="log"] > * {
            margin: 6px 0 !important;
        }
        .bubble-wrap [role="log"] > * > * {
            padding: 10px 14px !important;
            border-radius: 10px !important;
        }
        
        /* Scrollbar */
        ::-webkit-scrollbar {
            width: 8px;
        }
        
        ::-webkit-scrollbar-track {
            background: #f9fafb;
        }
        
        ::-webkit-scrollbar-thumb {
            background: #d1d5db;
            border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: #9ca3af;
        }
        
        /* Remove unnecessary padding */
        .input-row {
            gap: 0.5rem;
        }
        
        /* Responsive adjustments */
        @media (max-width: 768px) {
            .main-container {
                padding: 1rem;
            }
            
            .header h1 {
                font-size: 1.5rem;
            }
        }
    """,
    title="Finto Chat",
) as demo:
    with gr.Column(elem_classes="main-container"):
        # Header
        gr.Markdown(
            """
            <div class="header">
                <h1>🤖 Finto Chat</h1>
                <p>Your AI-powered chat assistant</p>
            </div>
            """
        )

        # New chat button
        with gr.Row(elem_classes="new-chat-container"):
            new_chat_btn = gr.Button(
                "➕ New Chat", variant="secondary", size="sm", scale=0, min_width=120
            )

        # Chat interface
        with gr.Column(elem_classes="chat-wrapper"):
            chatbot = gr.Chatbot(
                value=[],
                type="messages",
                height=650,
                show_label=False,
                avatar_images=(None, None),
                bubble_full_width=False,
                show_copy_button=True,
                layout="bubble",
            )

        # Input area
        with gr.Column(elem_classes="input-container"):
            with gr.Row(elem_classes="input-row"):
                msg = gr.Textbox(
                    placeholder="Type your message here...",
                    show_label=False,
                    container=False,
                    scale=20,
                    lines=1,
                    max_lines=5,
                )
                file_upload = gr.File(
                    label="📎",
                    file_types=["text", ".pdf", ".doc", ".docx", ".txt", ".md"],
                    type="filepath",
                    scale=0,
                    min_width=40,
                    elem_classes="file-upload-btn",
                )

            with gr.Row():
                submit_btn = gr.Button("Send", variant="primary", size="sm", scale=1)
                clear_btn = gr.Button("Clear", variant="secondary", size="sm", scale=1)

    # Event handlers
    async def submit_and_clear(message, file, history):
        """Submit message and clear the input box."""
        new_history = await send_message(message, file, history)
        return new_history, "", None

    # Submit on button click
    submit_btn.click(
        fn=submit_and_clear,
        inputs=[msg, file_upload, chatbot],
        outputs=[chatbot, msg, file_upload],
    )

    # Submit on Enter key
    msg.submit(
        fn=submit_and_clear,
        inputs=[msg, file_upload, chatbot],
        outputs=[chatbot, msg, file_upload],
    )

    # Clear chat history
    clear_btn.click(fn=clear_chat, outputs=chatbot)

    # New chat button
    new_chat_btn.click(fn=clear_chat, outputs=chatbot)


def launch_ui(share=False):
    """Launch the Gradio UI."""
    demo.launch(server_name="0.0.0.0", server_port=7860, share=share)


if __name__ == "__main__":
    launch_ui()
