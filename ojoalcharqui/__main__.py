"""`python -m ojoalcharqui` -> launch the localhost app."""
import webbrowser
import threading

import uvicorn


def main():
    host, port = "127.0.0.1", 8077
    url = f"http://{host}:{port}"
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    print(f"\n  ojo al charqui  →  {url}\n")
    uvicorn.run("ojoalcharqui.app.server:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
