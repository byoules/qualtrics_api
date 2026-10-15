# Qualtrics API Survey Export — 3 Ways (R, Python, or Google Apps Script)

> **This repository intentionally offers THREE DIFFERENT OPTIONS for the same task: R, Python, and Google Apps Script (JavaScript). Choose ONE language. You do NOT need to run all three.**
>
> Each option uses your Qualtrics API token to find accessible surveys, export a survey's responses, and save a CSV file. Pick the option that fits your environment and experience.

| Option | Choose it when... | Installation | Where `survey.csv` goes |
|---|---|---|---|
| **[1. R](#option-1-r-using-qualtrics)** | You already use R or RStudio or know `qualtRics`. | R + the `qualtRics` package | Current working directory on your computer |
| **[2. Python](#option-2-python)** | You want a reusable script with progress updates, command-line options, and streaming downloads. | Python 3.10+ + `requests` | `python/` folder by default (or a path you choose) |
| **[3. Google Apps Script](#option-3-google-apps-script-javascript)** | You want to run the export in your browser, with **no Python or R installation**. | None (requires a Google account) | **Google Drive**, not your PC |

All options use the **Qualtrics API**, rather than scraping survey webpages. By default, they request answer text labels, include breakouts and display-order information, use GMT for date/time exports, and export all available responses for the chosen survey. The Python and Apps Script versions remove Qualtrics' two extra CSV metadata header rows; R's `qualtRics` package manages its own import/column formatting. Resulting CSV files may not be byte-for-byte identical because `qualtRics` can transform some field types and names.

## Repository files

```text
qualtrics_api_3_options/
├── README.md                         # These instructions for ALL THREE choices
├── .gitignore                        # Excludes credentials and data exports
├── r/
│   └── qualtrics_export.R           # Option 1
├── python/
│   ├── qualtrics_export.py          # Option 2
│   └── requirements.txt             # Python dependency
└── google_apps_script/
    └── Code.gs                      # Option 3: copy into script.google.com
```

## What you need for any option

1. **Qualtrics API token.** Find or generate it in your Qualtrics account settings (assuming your organization grants API access).
2. **Your Qualtrics datacenter domain.** Example: `ca1.qualtrics.com`. Yours may be different. This is *not* necessarily the branded survey URL. See [Qualtrics API overview](https://www.qualtrics.com/support/integrations/api-integration/overview/).
3. **Survey ID.** Usually starts with `SV_`. Find it in the Qualtrics survey interface or use the built-in survey listing function.
4. Permission to export responses for the survey.

**Security:** Never publish a real API token, raw survey responses, or confidential participant data to a public GitHub repository. The `.gitignore` excludes common CSV files, but a previously committed file or other file type may still be visible. Use a secured local location or appropriately restricted Google Drive folder; follow your organization's policies for sharing respondent data and using cloud services.

---

## Option 1: R (using qualtRics)

**File:** [`r/qualtrics_export.R`](r/qualtrics_export.R)

This is the **original R approach** adapted into a reusable script. It uses `library(qualtRics)`, `qualtrics_api_credentials()`, `all_surveys()`, `fetch_survey()`, and `write.csv()`.

### R setup

1. Install [R](https://cran.r-project.org/) (RStudio is optional).
2. Open R/RStudio and install the package once:

   ```r
   install.packages("qualtRics")
   ```

3. Open `r/qualtrics_export.R` and change the API settings near the top:

   ```r
   API_KEY <- Sys.getenv("QUALTRICS_API_TOKEN", unset = "MYAPIKEY")
   BASE_URL <- Sys.getenv("QUALTRICS_BASE_URL", unset = "ca1.qualtrics.com/")
   SURVEY_ID <- Sys.getenv("QUALTRICS_SURVEY_ID", unset = "MYSURVEYID")
   ```

   Replace `MYAPIKEY` and `MYSURVEYID` with your actual values, inside quotation marks. Leave `ca1.qualtrics.com/` only if that is your correct domain. **If you intend to publish the repo, use environment variables instead of embedding your token in the script.**

### Run R

**In RStudio:** Open `qualtrics_export.R` and click **Source**.

**From a terminal in the repo root:**

```powershell
Rscript .\r\qualtrics_export.R
```

Or navigate to the `r` folder and run `Rscript qualtrics_export.R`. If `Rscript` is not recognized, run from RStudio or add R to your system PATH.

The script prints your accessible surveys, fetches the survey ID you selected, and creates `survey.csv` in **R's current working directory** (`getwd()`). To save beside the R script, run it after setting that folder as your working directory. Every export replaces the existing local CSV of the same name.

Optional settings near the top of the R script:

```r
SHOW_SURVEYS <- TRUE  # Print the survey list first
LIST_ONLY <- FALSE    # TRUE: only list surveys, no export
USE_LABELS <- TRUE    # TRUE: answer labels, FALSE: recoded values
OUTPUT_FILE <- "survey.csv"
```

### R without putting your API key in the file

In **PowerShell**, set the environment variables for this session before running R:

```powershell
$env:QUALTRICS_API_TOKEN = "your-real-token"
$env:QUALTRICS_BASE_URL = "ca1.qualtrics.com/"
$env:QUALTRICS_SURVEY_ID = "SV_your_survey_id"
Rscript .\r\qualtrics_export.R
```

Or inside the R session, set `Sys.setenv(QUALTRICS_API_TOKEN = "...", QUALTRICS_SURVEY_ID = "SV_...")` before sourcing the script.

---

## Option 2: Python

**Files:** [`python/qualtrics_export.py`](python/qualtrics_export.py) and [`python/requirements.txt`](python/requirements.txt)

This version directly calls the Qualtrics API using `requests`, waits for the response export to complete, downloads the ZIP, and writes a cleaned CSV. It does not need R, pandas, or Excel.

### Python setup on Windows

1. Install [Python 3.10 or newer](https://www.python.org/downloads/) if it isn't installed already.
2. Open **PowerShell in the repo's root folder** (the folder containing `README.md`).
3. Create a virtual environment and install the one dependency:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r .\python\requirements.txt
   ```

   This intentionally runs Python from the virtual environment **without activating** it, so you do not need to change PowerShell execution policy. Replace `py` with `python` if your machine does not have `py`.

4. Open `python/qualtrics_export.py` and edit these settings:

   ```python
   API_KEY = os.getenv("QUALTRICS_API_TOKEN", "MYAPIKEY")
   BASE_URL = os.getenv("QUALTRICS_BASE_URL", "ca1.qualtrics.com/")
   SURVEY_ID = os.getenv("QUALTRICS_SURVEY_ID", "MYSURVEYID")
   ```

### Run Python

```powershell
.\.venv\Scripts\python.exe .\python\qualtrics_export.py
```

The script lists surveys, logs export progress, and saves `python/survey.csv` by default. It overwrites an existing CSV after successfully preparing the replacement.

**Useful Python commands** (run from repo root):

| What you want | Command |
|---|---|
| **List survey names/IDs only** | `.\.venv\Scripts\python.exe .\python\qualtrics_export.py --list-only` |
| **Export a particular survey** | `.\.venv\Scripts\python.exe .\python\qualtrics_export.py --survey-id SV_123456789` |
| **Skip listing surveys** | `.\.venv\Scripts\python.exe .\python\qualtrics_export.py --no-list` |
| **Choose CSV file name** | `.\.venv\Scripts\python.exe .\python\qualtrics_export.py --output other_survey.csv` |
| **Export numeric recodes, not labels** | `.\.venv\Scripts\python.exe .\python\qualtrics_export.py --values` |
| **Keep all three original Qualtrics header rows** | `.\.venv\Scripts\python.exe .\python\qualtrics_export.py --raw` |

You can combine flags. For example: `--survey-id SV_123456789 --no-list --output C:\Data\export.csv`.

**Python environment-variable option:**

```powershell
$env:QUALTRICS_API_TOKEN = "your-real-token"
$env:QUALTRICS_BASE_URL = "ca1.qualtrics.com"
$env:QUALTRICS_SURVEY_ID = "SV_your_survey_id"
.\.venv\Scripts\python.exe .\python\qualtrics_export.py
```

On macOS/Linux, use `python3 -m venv .venv`, `.venv/bin/python -m pip install -r python/requirements.txt`, then `.venv/bin/python python/qualtrics_export.py`.

---

## Option 3: Google Apps Script (JavaScript)

**File:** [`google_apps_script/Code.gs`](google_apps_script/Code.gs)

This option runs **entirely through a browser** using JavaScript and Google's built-in services. You do not need to download or install Python, R, Node.js, or a command-line package. Your exported CSV ends up in **Google Drive**.

### Google Apps Script setup

1. Go to **[script.google.com](https://script.google.com/)** and create a **New project**.
2. Open [`google_apps_script/Code.gs`](google_apps_script/Code.gs) from this repository. Copy the **entire code** into the project's `Code.gs` editor, replacing any starter code. Save.
3. Near the top, edit:

   ```javascript
   BASE_URL: 'ca1.qualtrics.com',
   SURVEY_ID: 'MYSURVEYID',
   OUTPUT_FILE_NAME: 'survey.csv',
   DRIVE_FOLDER_ID: '',
   ```

   Change `SURVEY_ID` to your real `SV_...` ID and update `BASE_URL` if needed. Leaving `DRIVE_FOLDER_ID` blank saves to the **My Drive root**. To save in a specific existing folder, copy that folder's ID from its Google Drive URL (the text after `/folders/`) and set `DRIVE_FOLDER_ID` to it. The Google account running the script needs access to that folder.

4. In the left sidebar click **Project Settings** (gear icon). Under **Script Properties**, click **Add script property**. Save this exact property:

   | Property | Value |
   |---|---|
   | `QUALTRICS_API_TOKEN` | Your actual Qualtrics API token |

   **Do not add your API key directly to the JavaScript code.** Script Properties aren't a vault: other editors of this Apps Script project may be able to read them. Keep the project restricted.

5. Return to the **Editor** and choose `listSurveys` from the function selector at the top. Click **Run** and approve the authorization prompts for external requests/Drive access. Inspect the **Execution log** for survey IDs and names.
6. Select `exportSurvey` in the function selector and click **Run**. Inspect the Execution log for progress and a link to the finished CSV file.

Google Apps Script will make the Qualtrics API request, poll for export completion, unzip the response, remove extra CSV metadata rows (by default), and create `survey.csv` in the specified Google Drive location.

### Apps Script settings

At the top of `Code.gs` you can change:

```javascript
SHOW_SURVEYS_BEFORE_EXPORT: true, // Log the accessible survey list
USE_LABELS: true,                 // Text labels vs. numeric codes
REMOVE_EXTRA_HEADER_ROWS: true,   // Keep only the data header and response rows
OVERWRITE_EXISTING: true,         // Send previous same-named files to Drive Trash
```

**Important:** With `OVERWRITE_EXISTING: true`, the script creates the new CSV, then moves **any older files with the same name in the target folder** to Google Drive Trash. If you want to keep previous exports, set this to `false` or use a different `OUTPUT_FILE_NAME`. This is NOT a direct download to your Windows Downloads folder.

### Apps Script limitations

Google Apps Script is best for **smaller or moderate survey exports**. Google currently documents a **6-minute execution limit** and a **50 MB response limit per URL Fetch call**. The script polls for at most four minutes to leave time for download/conversion, but downloading and parsing very large exports can still time out or exceed memory limits. If that happens, use the R or Python option instead. See [Google's published quotas](https://developers.google.com/apps-script/guides/services/quotas).

---

## Shared export behavior and differences

| Feature | R | Python | Google Apps Script |
|---|---|---|---|
| List available surveys | `all_surveys()` | Startup or `--list-only` | Run `listSurveys()` |
| Export responses | `fetch_survey()` | Qualtrics export API | Qualtrics export API |
| Answer labels by default | Yes | Yes | Yes |
| Export in GMT | Yes | Yes | Yes |
| Keep one CSV header row | Yes, via `qualtRics` import/write | Yes, removes metadata rows | Yes, removes metadata rows |
| Run without installing programming language | No | No | **Yes** |
| Save on local computer | **Yes** | **Yes** | No — saves to Drive |
| Large-survey friendliness | Depends on available RAM | Streaming download and CSV write | Subject to Apps Script limits |

**CSV behavior:** Qualtrics' raw CSV usually starts with three records: column names, question text, and import IDs. Python and Apps Script default to keeping the **first** and dropping the next two. R delegates formatting to `qualtRics`. The Python `--raw` option and the Apps Script `REMOVE_EXTRA_HEADER_ROWS: false` setting preserve the Qualtrics original headers. If you plan to import the CSV back into Qualtrics, keep the native headers.

## Troubleshooting

- **401 or 403 / permission denied:** Check your token, correct datacenter, account permissions, and whether you can export that survey.
- **404 / export not found:** Check the `SV_...` ID and that the token has access to it; for errors after export completion, retry the export.
- **Survey list empty:** Your token might not have access to any surveys; verify survey ownership/sharing and permissions.
- **No `survey.csv` appears:** Check R's `getwd()`; Python defaults to `python/`; Apps Script writes to Google Drive, not your PC.
- **Apps Script authorization prompt:** `UrlFetchApp` and Google Drive operations require Google permissions. Run the function interactively once to approve access.
- **Apps Script timeout or too much memory:** Switch to Python or R.
- **Different dates, columns or labels across languages:** `qualtRics` may apply R-specific conversions and label handling that are not identical to the raw Qualtrics CSV export.
- **Sensitive respondent data:** Avoid public repos, shared folders, screenshots of responses, and leaving API tokens in committed scripts. Your organization may restrict sending respondent data to Google Drive.

## References

- [Qualtrics — Getting Started with the API](https://www.qualtrics.com/support/integrations/api-integration/overview/)
- [Qualtrics — Using Qualtrics API documentation](https://www.qualtrics.com/support/integrations/api-integration/using-qualtrics-api-documentation/)
- [Qualtrics REST API — List Surveys](https://www.postman.com/qualtrics-public-apis/qualtrics-public-workspace/request/kunakes/list-surveys)
- [Qualtrics REST API — Response Export File](https://www.postman.com/qualtrics-public-apis/qualtrics-public-workspace/request/14qa0qc/get-response-export-file)
- [qualtRics — `fetch_survey` documentation](https://search.r-project.org/CRAN/refmans/qualtRics/html/fetch_survey.html)
- [Google Apps Script — UrlFetchApp](https://developers.google.com/apps-script/reference/url-fetch/url-fetch-app)
- [Google Apps Script — Script Properties](https://developers.google.com/apps-script/guides/properties)
- [Google Apps Script — Utilities CSV/ZIP helpers](https://developers.google.com/apps-script/reference/utilities/utilities)

**Testing note:** The scripts have been checked locally for syntax, and CSV handling has been tested against sample Qualtrics-format data. They have **not** been authenticated against a live Qualtrics account; you will need your own token, datacenter, survey ID, and appropriate permissions.
