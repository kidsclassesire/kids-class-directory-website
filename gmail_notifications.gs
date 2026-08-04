// Google Apps Script Web App: sends claim-flow notification emails from your
// own Gmail account (GmailApp.sendEmail), triggered by a fire-and-forget
// fetch() from the static site (notify.js). No backend, no third-party email
// service, no secret keys in page source -- the only thing exposed client-side
// is this script's public Web App URL, which can only send these three fixed
// email shapes, not arbitrary mail.
//
// SETUP (one-time, ~5 minutes):
//   1. Go to https://script.google.com, click "New project".
//   2. Delete the placeholder code, paste this whole file in.
//   3. Change ADMIN_EMAIL below if you want claim alerts sent somewhere
//      other than the Google account you deploy this under.
//   4. Click Deploy > New deployment > gear icon > "Web app".
//        - Execute as: Me
//        - Who has access: Anyone
//   5. Click Deploy, authorize the requested Gmail-send permission (it'll
//      warn "Google hasn't verified this app" since it's your own personal
//      script -- click Advanced > Go to (project name) to proceed).
//   6. Copy the resulting Web App URL (ends in /exec).
//   7. Paste that URL into APPS_SCRIPT_URL at the top of notify.js in this
//      repo, then commit/push.
//
// To change the email wording later, edit this file, then Deploy > Manage
// deployments > edit (pencil) icon > New version > Deploy -- the URL stays
// the same, so no change needed on the notify.js side.

const ADMIN_EMAIL = 'davidmacmahon1@gmail.com';
const SITE_URL = 'https://www.kidspatch.ie';

function doPost(e) {
  try {
    const payload = JSON.parse(e.postData.contents);
    switch (payload.type) {
      case 'new_claim':
        sendNewClaimEmail(payload);
        break;
      case 'claim_approved':
        sendClaimApprovedEmail(payload);
        break;
      case 'claim_rejected':
        sendClaimRejectedEmail(payload);
        break;
    }
  } catch (err) {
    // Swallow errors -- this endpoint is best-effort (the claim itself is
    // already safely stored in Supabase regardless of whether this email
    // sends), and a thrown error here has no caller listening anyway since
    // the site calls this with fetch(..., {mode: 'no-cors'}).
  }
  return ContentService.createTextOutput('ok');
}

function sendNewClaimEmail(p) {
  const subject = `New claim request: ${p.business_name || 'Unknown business'}`;
  const body = [
    `A new "claim this business" request just came in on Kids Patch.`,
    ``,
    `Business: ${p.business_name || ''} (ID: ${p.business_id || ''})`,
    `Requester: ${p.requester_name || ''} (${p.requester_position || ''})`,
    `Email: ${p.requester_email || ''}`,
    ``,
    `Review it here: ${SITE_URL}/admin.html`,
  ].join('\n');
  GmailApp.sendEmail(ADMIN_EMAIL, subject, body);
}

function sendClaimApprovedEmail(p) {
  if (!p.requester_email) return;
  const subject = `Your Kids Patch claim for ${p.business_name || 'your business'} was approved`;
  const body = [
    `Good news -- your claim for "${p.business_name || 'your business'}" on Kids Patch has been approved.`,
    ``,
    `Manage your listing here: ${SITE_URL}/portal.html`,
    `Log in with the email address you used when you submitted the claim (${p.requester_email}).`,
    ``,
    `-- Kids Patch`,
  ].join('\n');
  GmailApp.sendEmail(p.requester_email, subject, body);
}

function sendClaimRejectedEmail(p) {
  if (!p.requester_email) return;
  const subject = `Your Kids Patch claim for ${p.business_name || 'your business'}`;
  const body = [
    `Thanks for your interest in claiming "${p.business_name || 'this business'}" on Kids Patch.`,
    `We weren't able to verify this claim, so it hasn't been approved.`,
    ``,
    `If you believe this is a mistake, reply to this email and we'll take another look.`,
    ``,
    `-- Kids Patch`,
  ].join('\n');
  GmailApp.sendEmail(p.requester_email, subject, body);
}
