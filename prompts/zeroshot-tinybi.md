Build a complete FastAPI project from scratch in a user-specified directory.

Goal:
Create a small but polished data analytics dashboard app that can be built and run locally within minutes. The app should let a user upload a CSV file and instantly see a dashboard with summary metrics, charts, a preview table, and simple auto-generated insights.

Important behavior:

* Ask the user where to create the project directory before starting.
* Ask the user for an app name at the beginning, suggesting "TinyBI" as the default.
* Limit follow-up questions strictly to these initial setup questions only (directory and app name). Do not ask additional questions afterward.
* Prefer creating the project in an empty or not-yet-existing folder.
* Make reasonable assumptions after the initial questions.
* Build everything needed from start to finish.
* Prefer a simple, working, polished app over complexity.
* Use FastAPI for the backend.
* Use plain HTML/CSS/JavaScript for the frontend.
* Use Chart.js via CDN for charts.
* Use pandas for CSV parsing.
* No database.
* No authentication.
* No external backend services.
* Use uv for dependency management instead of pip.
* Include a Makefile with common commands (e.g., `make serve` running `uv run uvicorn main:app --reload`).
* Include a simple API endpoint that allows modifying what is displayed on the dashboard (e.g., toggling metrics or charts), but keep it minimal so the app can still be built within 5 minutes.

Project structure:

* main.py
* pyproject.toml
* .gitignore
* Makefile
* README.md
* AGENTS.md
* templates/index.html
* static/styles.css
* static/app.js
* sample_data.csv

App name:
User-defined (default: TinyBI)

Core user flow:

1. User opens the homepage.
2. User sees a beautiful landing/dashboard page.
3. User can click upload a CSV file with uploads and automatically analyzes it.
4. The backend parses the CSV.
5. The frontend displays:

   * total rows
   * total columns
   * numeric columns detected
   * categorical columns detected
   * total sum for the primary numeric column
   * average value for the primary numeric column
   * minimum value
   * maximum value
   * best category if a categorical column exists
   * best date if a date column exists
   * CSV preview table
   * chart of values over time if a date column exists
   * bar chart by category if a categorical column exists
   * histogram or bar chart for numeric values
   * 3 to 5 plain-English insight cards

CSV assumptions:

* The app should automatically detect likely date columns.
* The app should automatically detect numeric columns.
* The app should automatically detect categorical columns.
* Use the first detected numeric column as the primary metric.
* Use the first detected date column as the time axis.
* Use the first detected categorical column as the grouping column.
* Handle missing values gracefully.
* Return useful errors for invalid files or empty CSVs.
* Include sample_data.csv with columns like date, category, revenue, users, region.

Sample data requirement:

* Fetch the sample data ZIP from [https://www.kaggle.com/api/v1/datasets/download/vivek468/superstore-dataset-final](https://www.kaggle.com/api/v1/datasets/download/vivek468/superstore-dataset-final).
* The downloaded file is a ZIP archive containing the CSV dataset.
* Extract the most relevant CSV from the ZIP and save it as `sample_data.csv` in the project root.
* If the download fails, create a small realistic fallback `sample_data.csv` and clearly mention the fallback in the final summary.

Notice: CSV encodings

* Do not assume uploaded CSV files or the Kaggle sample CSV are UTF-8 encoded.
* The Superstore sample can contain Windows/extended characters and may need encodings such as `cp1252` or `latin1`.
* Implement CSV parsing so it tries common encodings such as `utf-8`, `utf-8-sig`, `cp1252`, and `latin1` before returning a decode error.
* Keep the user-facing error clear if none of the supported encodings can decode the file.

Backend requirements:

* GET / returns the HTML page.
* POST /analyze accepts multipart file upload with field name “file”.
* POST /analyze returns JSON.
* Allow optional query parameters or request body fields to apply pandas .query(...) expressions to the dataset before analysis and plotting.
* Allow common plotting parameters (e.g., chart type, x/y columns, aggregation, sorting, limits) to be configurable via the request.
* Provide a simple POST /config endpoint that allows toggling which dashboard elements are shown (e.g., enable/disable charts or metrics).
* Use pandas to parse the CSV.
* Limit preview rows to 10.
* Limit chart rows to reasonable sizes.
* Include CORS only if needed.
* Add clean error handling with HTTPException.
* Keep logic readable and commented where helpful.

Frontend requirements:

* Modern dashboard look.
* Responsive layout.
* Drag-and-drop file upload area or a nice file input.
* Loading state while analyzing.
* Error state if upload fails.
* Metric cards.
* Insight cards.
* Chart.js charts.
* Preview table.
* Include a “Load sample data” button that analyzes the included sample_data.csv without needing the user to upload anything. Implement this either by serving the sample CSV statically and sending it to the same analyze endpoint from JS, or by adding a simple backend endpoint if easier.
* Optionally allow toggling dashboard elements via the simple config API.
* Keep the UI clean, not overengineered.

Visual style:

* SaaS analytics dashboard vibe.
* Rounded cards.
* Soft shadows.
* Clean typography.
* Nice spacing.
* Works well on laptop screen.
* No build step required.

AGENTS.md requirements:

* Create an AGENTS.md file at the root of the project.
* Include instructions that dependency management must be done using uv.
* Explicitly instruct:

  * Use `uv add <package>` for adding dependencies.
  * Use `uv add --dev <package>` for development dependencies.
* State that direct manual editing of pyproject.toml should be avoided when possible.
* Provide a short explanation of why uv is preferred (simplicity, reproducibility, speed).

README requirements:
Include:

* What the app does.
* How to install dependencies using uv.
* How to run it.
* Example commands:

  * `uv sync`
  * `make serve`
  * `uv run uvicorn main:app --reload`
* Mention opening [http://127.0.0.1:8000](http://127.0.0.1:8000)
* Explain the expected CSV format, but clarify that the app auto-detects columns.

Makefile requirements:

* Include common developer commands:

  * `make serve` → runs `uv run uvicorn main:app --reload`
  * `make install` → runs `uv sync`
* Keep it simple and readable.

After creating files:

* Run basic checks.
* Verify imports work.
* Ensure dependencies are correctly declared via uv.
* Make sure the app can run with `uv run uvicorn main:app --reload` or `make serve`.
* Fix any obvious bugs before finishing.

Git ignore requirement:

* Download `.gitignore` from [https://raw.githubusercontent.com/github/gitignore/refs/heads/main/Python.gitignore](https://raw.githubusercontent.com/github/gitignore/refs/heads/main/Python.gitignore) into the project root. Also add *.csv to `.gitignore`
* Do not hand-write a replacement unless the download fails; if it fails, clearly mention that fallback in the final summary.

Deliverable:
A complete working local FastAPI app in the user-specified directory. Do not stop after planning. Create the files, implement the app, and provide a concise final summary with run instructions.
