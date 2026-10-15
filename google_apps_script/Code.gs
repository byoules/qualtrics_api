/**
 * QUALTRICS SURVEY EXPORT - GOOGLE APPS SCRIPT (JavaScript)
 *
 * Option 3 of 3 in this repository. Runs in Google's cloud; no Python/R install.
 *
 * 1) Paste this file into a new project at https://script.google.com.
 * 2) Project Settings > Script Properties: add QUALTRICS_API_TOKEN = your token.
 * 3) Edit BASE_URL and SURVEY_ID below.
 * 4) Run listSurveys() to verify access, then run exportSurvey().
 *
 * Result: Google Drive file named survey.csv (not a file on your PC).
 * WARNING: Restrict project/Drive access if responses contain sensitive data.
 */

const CONFIG = {
  BASE_URL: 'ca1.qualtrics.com',  // Change for your Qualtrics datacenter
  SURVEY_ID: 'MYSURVEYID',       // Example: SV_123456789abcdef
  OUTPUT_FILE_NAME: 'survey.csv',
  DRIVE_FOLDER_ID: '',           // Blank = My Drive root. Or paste folder ID.
  SHOW_SURVEYS_BEFORE_EXPORT: true,
  USE_LABELS: true,              // true = text; false = numeric answer recodes
  TIME_ZONE: 'GMT',
  REMOVE_EXTRA_HEADER_ROWS: true,
  OVERWRITE_EXISTING: true,      // Moves older same-named CSV files to Drive Trash
  POLL_INTERVAL_MS: 2000,
  MAX_POLL_MS: 4 * 60 * 1000    // Apps Script has a ~6-minute execution limit
};

/** Run this first to log all surveys accessible to your token. */
function listSurveys() {
  const settings = getSettings_();
  const items = listSurveysInternal_(settings);
  console.log('Surveys accessible: ' + items.length);
  items.forEach(function(item) {
    console.log((item.id || '?') + ' | ' + (item.name || '(unnamed)'));
  });
  return items;
}

/** Main entry point: export a specified survey to a CSV in Google Drive. */
function exportSurvey() {
  const settings = getSettings_();
  const surveyId = CONFIG.SURVEY_ID.trim();
  if (!/^SV_[A-Za-z0-9_-]+$/.test(surveyId)) {
    throw new Error('Edit CONFIG.SURVEY_ID to your Qualtrics survey ID (SV_...).');
  }

  if (CONFIG.SHOW_SURVEYS_BEFORE_EXPORT) {
    const surveys = listSurveysInternal_(settings);
    console.log('Surveys accessible: ' + surveys.length);
    surveys.forEach(function(item) {
      console.log((item.id || '?') + ' | ' + (item.name || '(unnamed)'));
    });
  }

  const exportPath = '/surveys/' + encodeURIComponent(surveyId) + '/export-responses';
  console.log('Starting export for ' + surveyId + '...');
  const started = fetchJson_(settings, settings.apiRoot + exportPath, 'post', {
    format: 'csv',
    useLabels: CONFIG.USE_LABELS,
    timeZone: CONFIG.TIME_ZONE,
    breakoutSets: true,
    includeDisplayOrder: true
  });
  const progressId = started.result.progressId;
  if (!progressId) throw new Error('Qualtrics did not return a progressId.');

  const progressUrl = settings.apiRoot + exportPath + '/' + encodeURIComponent(progressId);
  const deadline = Date.now() + CONFIG.MAX_POLL_MS;
  let fileId = null;
  let lastPercent = null;
  while (Date.now() < deadline) {
    const response = fetchJson_(settings, progressUrl, 'get');
    const progress = response.result;
    const status = String(progress.status || '').toLowerCase();
    if (progress.percentComplete !== undefined && progress.percentComplete !== lastPercent) {
      console.log('Export progress: ' + progress.percentComplete + '%');
      lastPercent = progress.percentComplete;
    }
    if (status === 'failed' || status === 'error') {
      throw new Error('Qualtrics export failed: ' + JSON.stringify(progress));
    }
    if (status === 'complete' || status === 'completed') {
      fileId = progress.fileId;
      break;
    }
    Utilities.sleep(CONFIG.POLL_INTERVAL_MS);
  }
  if (!fileId) {
    throw new Error('Export did not complete in time. Try Python or R for large surveys.');
  }

  const fileUrl = settings.apiRoot + exportPath + '/' + encodeURIComponent(fileId) + '/file';
  console.log('Downloading ZIP from Qualtrics...');
  const download = fetchQualtrics_(settings, fileUrl, 'get');
  let entries;
  try {
    entries = Utilities.unzip(download.getBlob());
  } catch (error) {
    throw new Error('Qualtrics did not return a readable ZIP export: ' + error.message);
  }
  const csvEntries = entries.filter(function(blob) {
    return /\.csv$/i.test(blob.getName());
  });
  if (csvEntries.length !== 1) {
    throw new Error('Expected one CSV inside Qualtrics ZIP, got ' + csvEntries.length + '.');
  }

  let csv = csvEntries[0].getDataAsString('UTF-8').replace(/^\uFEFF/, '');
  let responseCount;
  if (CONFIG.REMOVE_EXTRA_HEADER_ROWS) {
    const rows = Utilities.parseCsv(csv);
    if (rows.length < 3) {
      throw new Error('Expected the three native Qualtrics CSV header rows.');
    }
    // Qualtrics CSV row 1 = variable names; row 2 = questions; row 3 = import IDs.
    // Work on parsed CSV records, NOT physical lines: answers can contain newlines.
    const cleanRows = [rows[0]].concat(rows.slice(3));
    csv = cleanRows.map(csvRow_).join('\r\n') + '\r\n';
    responseCount = cleanRows.length - 1;
  } else {
    responseCount = 'unknown (native three-row header format)';
  }

  // UTF-8 BOM helps Microsoft Excel correctly recognize non-ASCII characters.
  const csvBlob = Utilities.newBlob('\uFEFF' + csv, 'text/csv', CONFIG.OUTPUT_FILE_NAME);
  const folder = CONFIG.DRIVE_FOLDER_ID.trim()
    ? DriveApp.getFolderById(CONFIG.DRIVE_FOLDER_ID.trim())
    : DriveApp.getRootFolder();

  // Get old files before creating new, to avoid accidentally trashing the new file.
  const oldFiles = [];
  if (CONFIG.OVERWRITE_EXISTING) {
    const matches = folder.getFilesByName(CONFIG.OUTPUT_FILE_NAME);
    while (matches.hasNext()) oldFiles.push(matches.next());
  }

  const newFile = folder.createFile(csvBlob);
  oldFiles.forEach(function(file) { file.setTrashed(true); });
  console.log('Done! Saved ' + responseCount + ' responses.');
  console.log('Google Drive file: ' + newFile.getUrl());
  return newFile.getUrl();
}

/** Quote CSV fields properly (commas, quotes and multiline responses). */
function csvRow_(values) {
  return values.map(function(value) {
    const str = value === null || value === undefined ? '' : String(value);
    return /[",\r\n]/.test(str) ? '"' + str.replace(/"/g, '""') + '"' : str;
  }).join(',');
}

function getSettings_() {
  // Script Properties are convenient to set via Project Settings, but all
  // script editors can access them; only use in a restricted project.
  const token = PropertiesService.getScriptProperties().getProperty('QUALTRICS_API_TOKEN');
  if (!token || !token.trim()) {
    throw new Error('Set QUALTRICS_API_TOKEN in Project Settings > Script Properties.');
  }
  const host = CONFIG.BASE_URL.trim().replace(/^https:\/\//i, '').replace(/\/+$/, '');
  if (!/^[A-Za-z0-9.-]+\.qualtrics\.com$/i.test(host)) {
    throw new Error('BASE_URL should look like ca1.qualtrics.com (HTTPS only).');
  }
  return { token: token.trim(), apiRoot: 'https://' + host + '/API/v3' };
}

function listSurveysInternal_(settings) {
  let url = settings.apiRoot + '/surveys';
  const seen = {};
  const all = [];
  while (url) {
    if (seen[url]) throw new Error('Qualtrics pagination repeated a page.');
    seen[url] = true;
    const data = fetchJson_(settings, url, 'get');
    const result = data.result;
    if (!Array.isArray(result.elements)) {
      throw new Error('Unexpected Qualtrics survey list response.');
    }
    all.push.apply(all, result.elements);
    const nextPage = result.nextPage || (data.meta && data.meta.nextPage) || '';
    url = nextPage ? safeNextPageUrl_(settings.apiRoot, nextPage) : '';
  }
  return all;
}

function safeNextPageUrl_(apiRoot, nextPage) {
  let next = String(nextPage).trim();
  if (next.indexOf('https://') === 0) {
    if (next.indexOf(apiRoot + '/') !== 0) {
      throw new Error('Unexpected nextPage host or Qualtrics API path.');
    }
    return next;
  }
  if (next.charAt(0) === '?') return apiRoot + '/surveys' + next;
  if (next.indexOf('/API/v3/') === 0) {
    return apiRoot.split('/API/v3')[0] + next;
  }
  return apiRoot + '/' + next.replace(/^\/+/, '');
}

function fetchJson_(settings, url, method, payload) {
  const response = fetchQualtrics_(settings, url, method, payload);
  let json;
  try { json = JSON.parse(response.getContentText('UTF-8')); }
  catch (err) { throw new Error('Qualtrics returned an unexpected non-JSON response.'); }
  if (!json || !json.result || typeof json.result !== 'object') {
    throw new Error('Qualtrics response had no expected result object.');
  }
  return json;
}

function fetchQualtrics_(settings, url, method, payload) {
  // Never forward the API token to an unfamiliar host.
  if (url.indexOf(settings.apiRoot + '/') !== 0) {
    throw new Error('Blocked API request to unexpected URL.');
  }
  const options = {
    method: method,
    headers: { 'X-API-TOKEN': settings.token, 'Accept': 'application/json' },
    muteHttpExceptions: true,
    followRedirects: false
  };
  if (payload !== undefined) {
    options.contentType = 'application/json';
    options.payload = JSON.stringify(payload);
  }
  const response = UrlFetchApp.fetch(url, options);
  const code = response.getResponseCode();
  if (code < 200 || code >= 300) {
    let message = response.getContentText('UTF-8').slice(0, 300);
    throw new Error('Qualtrics returned HTTP ' + code + ': ' + message);
  }
  return response;
}
