import ctypes

from flask import Flask

from routes.web import web
from routes.api import api

def enable_dpi_awareness():
    """Keep pynput coordinates aligned with Windows' virtual desktop pixels."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware.
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


enable_dpi_awareness()
app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False
app.register_blueprint(web)
app.register_blueprint(api)

if __name__ == "__main__":
    app.run(debug=False, use_reloader=False)
