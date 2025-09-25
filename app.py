import os
import sys
import threading
from typing import Any, Dict

import webview
from pathlib import Path
import tkinter as tk

from module.automation.post_mode import post_run
from module.bot.gemini_post_fb import gemini_post_generate


def load_ui_html() -> str:
    root = Path(__file__).resolve().parent
    ui_path = root / "ui" / "index.html"
    with ui_path.open("r", encoding="utf-8") as f:
        return f.read()


class UiLogStream:
    def __init__(self, window: webview.Window) -> None:
        self.window = window
        self._buffer = ""

    def write(self, data: str) -> int:
        if not isinstance(data, str):
            data = str(data)
        self._buffer += data
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            try:
                safe = line.replace("\\", "\\\\").replace("'", "\\'")
                self.window.evaluate_js(f"window.__appendLog('{safe}')")
            except Exception:
                pass
        return len(data)

    def flush(self) -> None:
        if self._buffer:
            try:
                safe = self._buffer.replace("\\", "\\\\").replace("'", "\\'")
                self.window.evaluate_js(f"window.__appendLog('{safe}')")
            except Exception:
                pass
            self._buffer = ""


class Api:
    def __init__(self) -> None:
        self._has_run = False
        self._lock = threading.Lock()
        self._window: webview.Window | None = None
        self._stop_event = threading.Event()
        self._worker_thread: threading.Thread | None = None

    def run_once(self, user_id: str, context: str = "", api_key: str = "", model: str = "", schedule: list | None = None, settings: dict | None = None) -> Dict[str, Any]:  # called from JS
        
        with self._lock:
            if self._has_run:
                return {"success": False, "error": "Đã chạy rồi."}
            self._has_run = True

        def worker():
            try:
                # Reset stop flag
                self._stop_event.clear()
                # Redirect stdout/stderr to UI during the run
                old_out, old_err = sys.stdout, sys.stderr
                if self._window is not None:
                    ui_stream = UiLogStream(self._window)
                    sys.stdout = ui_stream
                    sys.stderr = ui_stream
                try:
                    # Pass stop_event to worker for cooperative cancellation
                    post_run(user_id=user_id, context=context, api_key=api_key, model=model, schedule=schedule or [], settings=settings or {}, stop_event=self._stop_event)
                finally:
                    sys.stdout = old_out
                    sys.stderr = old_err
            except Exception as exc:
                # allow retry on failure
                with self._lock:
                    self._has_run = False
                raise exc

        try:
            # Start worker in separate thread
            self._worker_thread = threading.Thread(target=worker, daemon=True)
            self._worker_thread.start()
            self._worker_thread.join()  # Wait for completion
            
            return {"success": True, "contextEcho": context}
        except Exception as exc:
            # allow retry on failure
            with self._lock:
                self._has_run = False
            return {"success": False, "error": str(exc)}

    def share_cheo(self, user_id: str) -> Dict[str, Any]:  # called from JS
        try:
            old_out, old_err = sys.stdout, sys.stderr
            if self._window is not None:
                ui_stream = UiLogStream(self._window)
                sys.stdout = ui_stream
                sys.stderr = ui_stream
            try:
                # Placeholder: reuse post_run for now until share logic is implemented
                print("Developing..")
            finally:
                sys.stdout = old_out
                sys.stderr = old_err
            return {"success": True, "message": "Share chéo đã chạy."}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def like_cheo(self, user_id: str) -> Dict[str, Any]:  # called from JS
        try:
            old_out, old_err = sys.stdout, sys.stderr
            if self._window is not None:
                ui_stream = UiLogStream(self._window)
                sys.stdout = ui_stream
                sys.stderr = ui_stream
            try:
                # Placeholder: reuse post_run for now until like logic is implemented
                print("Developing..")
            finally:
                sys.stdout = old_out
                sys.stderr = old_err
            return {"success": True, "message": "Like chéo đã chạy."}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def stop_run(self) -> Dict[str, Any]:  # called from JS
        try:
            self._stop_event.set()
            
            # Force kill the worker thread if it exists
            if self._worker_thread and self._worker_thread.is_alive():
                # Note: Python doesn't support forceful thread termination
                # But we can try to interrupt it by setting the stop event
                # and the thread should check this event regularly
                print("Stop signal sent to worker thread")
                
            with self._lock:
                self._has_run = False
            return {"success": True}
        except Exception as exc:
            return {"success": False, "error": str(exc)}


def main() -> None:
    api = Api()
    # Calculate 3/4 of the current screen size and center the window
    _tk = tk.Tk()
    _tk.withdraw()
    screen_w = _tk.winfo_screenwidth()
    screen_h = _tk.winfo_screenheight()
    _tk.destroy()
    win_w = int(screen_w * 0.75)
    win_h = int(screen_h * 0.75)
    pos_x = (screen_w - win_w) // 2
    pos_y = (screen_h - win_h) // 2
    window = webview.create_window(
        title="AdsPower Poster",
        html=load_ui_html(),
        width=900,
        height=1200,
        x=pos_x,
        y=pos_y,
        resizable=True,
        js_api=api,
    )
    api._window = window
    webview.start(gui="edgechromium", http_server=True, debug=False, private_mode=False)


if __name__ == "__main__":
    main()


