"""List Qualtrics surveys and export one survey's responses to CSV.

Python 3.10+ | Requires: requests

Edit the settings below, then run:
    python qualtrics_export.py

Alternative (without putting the token in this file):
    $env:QUALTRICS_API_TOKEN = "your_token"
    $env:QUALTRICS_SURVEY_ID = "SV_your_survey_id"
    python qualtrics_export.py
"""

import argparse
import csv
import os
import shutil
import sys
import tempfile
import time
import zipfile
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# ======================== CHANGE THESE SETTINGS ========================
API_KEY = os.getenv("QUALTRICS_API_TOKEN", "MYAPIKEY")
BASE_URL = os.getenv("QUALTRICS_BASE_URL", "ca1.qualtrics.com/")
SURVEY_ID = os.getenv("QUALTRICS_SURVEY_ID", "MYSURVEYID")

TIME_ZONE = "GMT"                 # Same intent as Sys.setenv(TZ = "GMT") in R
SHOW_SURVEYS = True              # False = skip displaying your survey list
USE_LABELS = True               # True = answer text; False = numeric recode values
OUTPUT_FILE = "survey.csv"      # Saved beside this Python script by default

# Qualtrics CSV includes 3 header rows. R's fetch_survey() removes rows 2-3.
REMOVE_EXTRA_HEADER_ROWS = True
MAX_EXPORT_WAIT_SECONDS = 600
POLL_EVERY_SECONDS = 2
# ======================================================================


class QualtricsError(RuntimeError):
    """Friendly error for Qualtrics API and download failures."""


def make_base_url(base_url: str) -> str:
    value = base_url.strip().rstrip("/")
    if not value.startswith(("https://", "http://")):
        value = "https://" + value
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname:
        raise QualtricsError("BASE_URL must be a valid HTTPS Qualtrics address.")
    # Prevent accidentally sending an API token to a different website.
    if not (parsed.hostname == "qualtrics.com" or parsed.hostname.endswith(".qualtrics.com")):
        raise QualtricsError("BASE_URL must use a qualtrics.com hostname.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise QualtricsError("BASE_URL should contain only your Qualtrics domain.")
    if parsed.path and parsed.path.rstrip("/") not in ("", "/API/v3"):
        raise QualtricsError("BASE_URL must not contain a URL path other than /API/v3.")
    return f"https://{parsed.netloc}/API/v3"


def make_session(api_key: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "X-API-TOKEN": api_key,
        "Accept": "application/json",
    })
    retries = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(("GET", "POST")),
        respect_retry_after_header=True,
    )
    session.mount("https://", HTTPAdapter(max_retries=retries))
    return session


def check_response(response: requests.Response) -> None:
    try:
        response.raise_for_status()
    except requests.HTTPError as error:
        detail = ""
        try:
            payload = response.json()
            error_info = payload.get("meta", {}).get("error", {})
            detail = error_info.get("errorMessage") or payload.get("message") or ""
        except (ValueError, AttributeError, TypeError):
            pass
        hint = (
            " Verify your API key, Qualtrics datacenter/base URL, survey ID, "
            "and export permissions."
            if response.status_code in (400, 401, 403, 404) else ""
        )
        raise QualtricsError(
            f"Qualtrics returned HTTP {response.status_code}. {detail}{hint}"
        ) from error


def request_json(session: requests.Session, method: str, url: str, **kwargs) -> dict:
    with session.request(method, url, timeout=(15, 90), **kwargs) as response:
        check_response(response)
        try:
            payload = response.json()
        except ValueError as error:
            raise QualtricsError("Qualtrics returned an unexpected non-JSON response.") from error
        if not isinstance(payload, dict) or not isinstance(payload.get("result"), dict):
            raise QualtricsError(f"Unexpected Qualtrics API response at: {url.split('?')[0]}")
        return payload


def list_surveys(session: requests.Session, base_api_url: str) -> list[dict]:
    """Follow Qualtrics pagination to include every accessible survey."""
    url = base_api_url + "/surveys"
    surveys: list[dict] = []
    visited: set[str] = set()
    while url:
        if url in visited:
            raise QualtricsError("Qualtrics survey pagination repeated the same page.")
        visited.add(url)
        response = request_json(session, "GET", url)
        result = response["result"]
        surveys.extend(result.get("elements") or [])
        next_page = result.get("nextPage") or response.get("meta", {}).get("nextPage")
        if not next_page:
            break
        next_url = urljoin(url, next_page)
        if urlparse(next_url).netloc != urlparse(base_api_url).netloc:
            raise QualtricsError("Unexpected Qualtrics pagination URL hostname.")
        url = next_url
    return surveys


def start_export(session: requests.Session, base_api_url: str, survey_id: str, labels: bool) -> str:
    url = f"{base_api_url}/surveys/{survey_id}/export-responses"
    # R qualtRics::fetch_survey() defaults: labels, breakout sets, display order.
    options = {
        "format": "csv",
        "useLabels": labels,
        "timeZone": TIME_ZONE,
        "breakoutSets": True,
        "includeDisplayOrder": True,
    }
    payload = request_json(session, "POST", url, json=options)
    progress_id = payload["result"].get("progressId")
    if not progress_id:
        raise QualtricsError("Qualtrics did not return an export progress ID.")
    return progress_id


def wait_for_export(session: requests.Session, base_api_url: str, survey_id: str, progress_id: str) -> str:
    url = f"{base_api_url}/surveys/{survey_id}/export-responses/{progress_id}"
    deadline = time.monotonic() + MAX_EXPORT_WAIT_SECONDS
    last_percent = None
    while time.monotonic() < deadline:
        payload = request_json(session, "GET", url)
        info = payload["result"]
        status = str(info.get("status", "")).lower()
        percent = info.get("percentComplete")
        if percent is not None and percent != last_percent:
            print(f"  Export progress: {percent}%")
            last_percent = percent
        if status in ("failed", "error"):
            raise QualtricsError(f"Qualtrics export failed: {info}")
        if status in ("complete", "completed"):
            file_id = info.get("fileId")
            if not file_id:
                raise QualtricsError("Export completed but no download file ID was returned.")
            return file_id
        time.sleep(POLL_EVERY_SECONDS)
    raise QualtricsError("Export did not finish within 10 minutes. Try again later.")


@contextmanager
def downloaded_temp_file(session: requests.Session, url: str):
    """Stream large response files to disk rather than loading into RAM."""
    temporary_path = None
    try:
        with session.get(url, stream=True, timeout=(15, 180)) as response:
            check_response(response)
            with tempfile.NamedTemporaryFile(prefix="qualtrics_download_", suffix=".tmp", delete=False) as temp:
                temporary_path = Path(temp.name)
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        temp.write(chunk)
        yield temporary_path
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def write_clean_csv(source, output: Path, remove_extra_header_rows: bool) -> int:
    """Copy records safely (including quoted multi-line answers) to final CSV."""
    # 'source' is a binary file object, either from ZIP or a raw CSV.
    import io
    with io.TextIOWrapper(source, encoding="utf-8-sig", newline="") as text_in:
        reader = csv.reader(text_in)
        with output.open("w", encoding="utf-8-sig", newline="") as file_out:
            writer = csv.writer(file_out)
            header = next(reader, None)
            if header is None:
                raise QualtricsError("The downloaded CSV is empty.")
            writer.writerow(header)
            if remove_extra_header_rows:
                # CSV row 2 = question text; CSV row 3 = import IDs.
                next(reader, None)
                next(reader, None)
            count = 0
            for row in reader:
                writer.writerow(row)
                count += 1
    return count


def save_export_as_csv(download_path: Path, output_path: Path, remove_headers: bool) -> int:
    """Extract a CSV from ZIP (or read direct CSV), then atomically save it."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix="qualtrics_csv_", suffix=".csv", dir=output_path.parent, delete=False
        ) as tmp:
            temporary_output = Path(tmp.name)

        if zipfile.is_zipfile(download_path):
            with zipfile.ZipFile(download_path) as archive:
                csv_files = [item for item in archive.infolist()
                             if not item.is_dir() and item.filename.lower().endswith(".csv")]
                if not csv_files:
                    raise QualtricsError("Qualtrics ZIP archive did not contain a CSV file.")
                if len(csv_files) > 1:
                    raise QualtricsError("Qualtrics ZIP contained multiple CSV files; cannot choose safely.")
                with archive.open(csv_files[0]) as source:
                    count = write_clean_csv(source, temporary_output, remove_headers)
        else:
            with download_path.open("rb") as source:
                count = write_clean_csv(source, temporary_output, remove_headers)
        # Avoid a partial survey.csv if an export or CSV parsing error occurred.
        os.replace(temporary_output, output_path)
        temporary_output = None
        return count
    finally:
        if temporary_output is not None:
            temporary_output.unlink(missing_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="List Qualtrics surveys and export responses to CSV.")
    parser.add_argument("--list-only", action="store_true", help="Show surveys; do not download responses.")
    parser.add_argument("--survey-id", default=SURVEY_ID, help="Override SURVEY_ID in the settings.")
    parser.add_argument("--output", default=OUTPUT_FILE, help="CSV file name or full path.")
    parser.add_argument("--values", action="store_true", help="Export numeric recode values instead of answer labels.")
    parser.add_argument("--raw", action="store_true", help="Keep all three native Qualtrics CSV header rows.")
    parser.add_argument("--no-list", action="store_true", help="Do not print the list of available surveys.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not API_KEY.strip() or API_KEY.strip() == "MYAPIKEY":
        raise QualtricsError(
            "Set API_KEY near the top of the script, or set the QUALTRICS_API_TOKEN environment variable."
        )
    base_api_url = make_base_url(BASE_URL)
    survey_id = args.survey_id.strip()

    session = make_session(API_KEY.strip())
    try:
        print(f"Qualtrics server: {urlparse(base_api_url).netloc}")
        if args.list_only or (SHOW_SURVEYS and not args.no_list):
            print("\nAvailable surveys:")
            surveys = list_surveys(session, base_api_url)
            if not surveys:
                print("  (No surveys accessible with this API token)")
            for item in surveys:
                print(f"  {item.get('id', '?')}  |  {item.get('name', '(unnamed)')}")
            print(f"Total surveys: {len(surveys)}")

        if args.list_only:
            return 0

        if not survey_id or survey_id == "MYSURVEYID":
            raise QualtricsError("Set SURVEY_ID near the top of the script or use --survey-id SV_...")
        if not survey_id.startswith("SV_") or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-" for c in survey_id):
            raise QualtricsError("Invalid survey ID. It usually starts with SV_.")

        print(f"\nStarting CSV export for {survey_id}...")
        progress_id = start_export(session, base_api_url, survey_id, labels=(USE_LABELS and not args.values))
        file_id = wait_for_export(session, base_api_url, survey_id, progress_id)
        download_url = f"{base_api_url}/surveys/{survey_id}/export-responses/{file_id}/file"

        output_path = Path(args.output).expanduser()
        if not output_path.is_absolute():
            output_path = Path(__file__).resolve().parent / output_path
        output_path = output_path.resolve()

        print("Downloading and preparing CSV...")
        with downloaded_temp_file(session, download_url) as download_path:
            count = save_export_as_csv(
                download_path, output_path,
                remove_headers=(REMOVE_EXTRA_HEADER_ROWS and not args.raw),
            )
        print(f"\nSuccess! Saved {count:,} response rows to:\n{output_path}")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (QualtricsError, requests.RequestException, OSError, csv.Error, zipfile.BadZipFile) as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)
