# Qualtrics survey export in R (qualtRics)
#
# One of three equivalent options in this repo:
#   r/qualtrics_export.R
#   python/qualtrics_export.py
#   google_apps_script/Code.gs
#
# FIRST TIME ONLY: in R / RStudio, run install.packages("qualtRics")
# RUN: Rscript qualtrics_export.R   (or open in RStudio and Source)
#
# You can edit MYAPIKEY/MYSURVEYID below, or use environment variables
# QUALTRICS_API_TOKEN, QUALTRICS_SURVEY_ID, and QUALTRICS_BASE_URL.
# Never commit actual credentials or respondent data to GitHub.

library(qualtRics)

# ======================== CHANGE THESE SETTINGS ========================
API_KEY <- Sys.getenv("QUALTRICS_API_TOKEN", unset = "MYAPIKEY")
BASE_URL <- Sys.getenv("QUALTRICS_BASE_URL", unset = "ca1.qualtrics.com/")
SURVEY_ID <- Sys.getenv("QUALTRICS_SURVEY_ID", unset = "MYSURVEYID")

SHOW_SURVEYS <- TRUE           # FALSE = skip listing accessible surveys
LIST_ONLY <- FALSE             # TRUE = list accessible surveys and do not export
USE_LABELS <- TRUE             # TRUE = answer text, FALSE = recoded values
OUTPUT_FILE <- "survey.csv"   # Created in the current working directory
# =======================================================================

if (!nzchar(API_KEY) || API_KEY == "MYAPIKEY") {
  stop("Set API_KEY above or the QUALTRICS_API_TOKEN environment variable.")
}

# Register Qualtrics credentials (same as the original R example).
qualtrics_api_credentials(api_key = API_KEY, base_url = BASE_URL)

# Optional: inspect the survey IDs available to your Qualtrics API token.
if (SHOW_SURVEYS || LIST_ONLY) {
  surveys <- all_surveys()
  print(surveys)
}

if (!LIST_ONLY) {
  if (!nzchar(SURVEY_ID) || SURVEY_ID == "MYSURVEYID") {
    stop("Set SURVEY_ID above or the QUALTRICS_SURVEY_ID environment variable.")
  }

  # Set GMT to match the original example; also explicitly request GMT data.
  Sys.setenv(TZ = "GMT")

  # fetch_survey downloads the complete survey and converts it to an R data frame.
  mysurvey <- fetch_survey(
    surveyID = SURVEY_ID,
    time_zone = "GMT",
    label = USE_LABELS,
    breakout_sets = TRUE,
    include_display_order = TRUE
  )

  # Save without an extra R row-number column.
  write.csv(mysurvey, file = OUTPUT_FILE, row.names = FALSE, fileEncoding = "UTF-8")
  cat(sprintf("Success! Saved %d responses to %s\n",
              nrow(mysurvey), normalizePath(OUTPUT_FILE)))
}
