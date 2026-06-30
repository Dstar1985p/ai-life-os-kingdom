"""
Kingdom Desktop App — double-click to launch.
Starts the FastAPI server in a background thread, then opens a native window.
"""
import sys
import os
import threading
import time
import webbrowser

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PORT = 8765
URL = f"http://127.0.0.1:{PORT}"


def start_server():
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="127.0.0.1",
        port=PORT,
        log_level="error",
    )


def wait_for_server(timeout=30):
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"{URL}/health", timeout=1)
            return True
        except Exception:
            time.sleep(0.3)
    return False


def main():
    # Start server in background thread
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    # Try to open in a native webview window first
    try:
        import webview  # pywebview

        # Wait for server to be ready
        if not wait_for_server():
            raise RuntimeError("Server did not start in time")

        window = webview.create_window(
            "🏰 Kingdom — AI Life OS",
            URL,
            width=1400,
            height=900,
            min_size=(900, 600),
            background_color="#030010",
        )
        webview.start(debug=False)

    except ImportError:
        # pywebview not installed — fall back to browser
        print("Opening Kingdom in your browser...")
        if not wait_for_server():
            print("ERROR: Server failed to start. Check that all dependencies are installed.")
            input("Press Enter to exit...")
            sys.exit(1)
        webbrowser.open(URL)
        print(f"Kingdom is running at {URL}")
        print("Close this window to shut down the Kingdom.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
