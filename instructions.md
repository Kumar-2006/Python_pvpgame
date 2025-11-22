# Multiplayer Setup Instructions

## 1. PythonAnywhere Deployment (Server)

To host the game server on PythonAnywhere:

1.  **Sign Up/Log In**: Go to [PythonAnywhere](https://www.pythonanywhere.com/) and create a free account.
2.  **Upload Files**:
    *   Go to the "Files" tab.
    *   Upload `server.py` and `shared_logic.py` to your home directory (e.g., `/home/yourusername/`).
3.  **Install Flask**:
    *   Open a "Bash" console from the "Consoles" tab.
    *   Run: `pip install flask --user`
4.  **Configure Web App**:
    *   Go to the "Web" tab.
    *   Click "Add a new web app".
    *   Choose "Flask" -> "Python 3.x" (latest).
    *   **Important**: In the "Code" section of the Web tab:
        *   **Source code**: `/home/yourusername/`
        *   **WSGI configuration file**: Click the link to edit it.
        *   Delete everything and paste this:
            ```python
            import sys
            import os

            # Add your project directory to the sys.path
            project_home = '/home/yourusername'
            if project_home not in sys.path:
                sys.path = [project_home] + sys.path

            # Import flask app but need to call it "application" for WSGI to work
            from server import app as application
            ```
            *(Replace `yourusername` with your actual PythonAnywhere username)*.
    *   Save the file.
5.  **Reload**: Go back to the "Web" tab and click the green "Reload" button.
6.  **Get URL**: Your server URL will be `http://yourusername.pythonanywhere.com`.

## 2. Client Configuration

1.  Open `game.py` locally.
2.  Find the `NetworkClient` class (around line 120).
3.  Change the `base_url` default value to your PythonAnywhere URL:
    ```python
    class NetworkClient:
        def __init__(self, base_url="http://yourusername.pythonanywhere.com"):
            # ...
    ```
    *(Alternatively, you can keep it as `http://127.0.0.1:5000` for local testing)*.

## 3. How to Play

1.  **Start Server**: Ensure your PythonAnywhere web app is running (or run `python server.py` locally).
2.  **Player 1 (Host)**:
    *   Run `python game.py`.
    *   Click **MULTIPLAYER**.
    *   Click **CREATE GAME**.
    *   Select your team and confirm.
    *   You will see a **GAME ID** (e.g., `A1B2C3`). Share this with Player 2.
    *   Wait in the lobby.
3.  **Player 2 (Joiner)**:
    *   Run `python game.py`.
    *   Click **MULTIPLAYER**.
    *   Click **JOIN GAME**.
    *   Type the **GAME ID** and press Enter.
    *   Select your team and confirm.
4.  **Battle**:
    *   The game will start.
    *   Turns are synchronized via the server.
## Troubleshooting

### "Address already in use" Error
If you see this error in the PythonAnywhere console:
`OSError: [Errno 98] Address already in use`

**STOP!** You are trying to run the server manually (e.g., `python server.py`).
**On PythonAnywhere, you do NOT run the script manually.**
1.  Close the console.
2.  Go to the **Web** tab.
3.  Click the green **Reload** button.
4.  That's it! The server is running in the background.

### "Unhandled Exception" / 404 Error
If you see "Unhandled Exception" in the browser:
1.  **Check the Error Log**:
    *   Go to the **Web** tab.
    *   Scroll down to **Log files**.
    *   Click **Error log**.
    *   Scroll to the bottom to see the specific error.
2.  **Check File Paths (Case Sensitive!)**:
    *   Linux is case-sensitive. `/home/JonathanSamson` is different from `/home/jonathansamson`.
    *   Check your **WSGI Configuration** file.
    *   If your files are in a folder like `mysite`, make sure the path includes it:
        ```python
        project_home = '/home/JonathanSamson/mysite' # Example
        ```
3.  **Missing Files**:
    *   Ensure `server.py` AND `shared_logic.py` are in the SAME folder.
