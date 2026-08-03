// Google Apps Script — event-driven site rebuild for renoncement.fr.
//
// Bound to the responses spreadsheet, this fires a GitHub workflow_dispatch
// the moment a REX (or a report) is submitted, or when any cell is edited
// (e.g. ticking the "Validé" moderation checkbox). The site therefore
// updates within minutes of the event instead of waiting for a cron slot.
//
// Installation: see SETUP.md, step I. Requires:
//   - script property GITHUB_PAT: fine-grained token, this repo only,
//     permission "Actions: Read and write", nothing else;
//   - two INSTALLABLE triggers (simple triggers cannot call UrlFetchApp):
//       onFormSubmitTrigger  -> From spreadsheet -> On form submit
//       onEditTrigger        -> From spreadsheet -> On edit
//
// Log hygiene mirrors sync.py: nothing from the sheet is ever sent or
// logged — the dispatch payload is only {"ref": "main"}.

const REPO = "TLavocat/renoncement.fr";
const WORKFLOW = "sync-and-deploy.yml";
const DEBOUNCE_SECONDS = 120; // burst of edits -> one dispatch

function onFormSubmitTrigger(e) {
  dispatch_();
}

function onEditTrigger(e) {
  dispatch_();
}

function dispatch_() {
  const props = PropertiesService.getScriptProperties();
  const last = Number(props.getProperty("lastDispatch") || 0);
  const now = Date.now();
  if (now - last < DEBOUNCE_SECONDS * 1000) return;
  props.setProperty("lastDispatch", String(now));

  const token = props.getProperty("GITHUB_PAT");
  if (!token) throw new Error("Script property GITHUB_PAT is not set");

  UrlFetchApp.fetch(
    "https://api.github.com/repos/" + REPO + "/actions/workflows/" + WORKFLOW + "/dispatches",
    {
      method: "post",
      headers: {
        Authorization: "Bearer " + token,
        Accept: "application/vnd.github+json",
      },
      contentType: "application/json",
      payload: JSON.stringify({ ref: "main" }),
    }
  );
}
