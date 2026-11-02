# Project Name (e.g., Macro App)

A brief, one-sentence description of what your application does (e.g., "A Python-based Flask application built for the odd semester final project to automate macros.").

##  Tech Stack
* **Language:** Python 3.x
* **Framework:** Flask
* **Libraries:** `ctypes` (for Windows DPI handling)

## Setup & Installation

Follow these steps to run the project locally on your machine.

### 1. Clone the Repository
```bash
git clone https://github.com
cd YOUR-REPO-NAME
```

### 2. Set Up a Virtual Environment
```bash
python -m venv .venv
```

* **Windows (PowerShell):**
  ```powershell
  .venv\Scripts\Activate.ps1
  ```
* **Mac/Linux:**
  ```bash
  source .venv/bin/activate
  ```

### 3. Install Dependencies
*(If you have a requirements.txt file, list it here)*
```bash
pip install flask
```

### 4. Environment Variables
Create a local `.env` file in the root directory (remember, this file is ignored by Git and should not be shared) and add your keys:
```text
FLASK_ENV=development
# Add any other secret keys here
```

## How to Run the App
Start the Flask development server:
```bash
python app.py
```
Open your browser and navigate to `http://127.0.0.1:5000`.
