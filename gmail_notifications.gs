// Google Apps Script Web App: sends claim-flow notification emails from
// info@kidspatch.ie (GmailApp.sendEmail, run under that Google Workspace
// account), triggered by a fire-and-forget fetch() from the static site
// (notify.js). No backend, no third-party email service, no secret keys in
// page source -- the only thing exposed client-side is this script's public
// Web App URL.
//
// That URL sitting in public JS source means anyone can POST to it directly
// (not just this site), so every send is gated on claimRequestExists() below
// actually finding a matching row in Supabase first -- otherwise this would
// be an open relay letting anyone make info@kidspatch.ie email an arbitrary
// address ("your claim was approved, log in at portal.html...") on demand.
//
// SETUP (one-time, ~5 minutes):
//   1. Log into Google as info@kidspatch.ie (not your personal account).
//   2. Go to https://script.google.com, click "New project".
//   3. Delete the placeholder code, paste this whole file in.
//   4. Project Settings (gear icon) > Script Properties > add
//      SUPABASE_SERVICE_ROLE_KEY = <service_role key from Supabase
//      Project Settings > API>. This key bypasses RLS, which is required
//      here (this script has no end-user session/JWT to satisfy the normal
//      claim_requests policies) -- it must live ONLY in Script Properties,
//      never in this file or the site repo.
//   5. Click Deploy > New deployment > gear icon > "Web app".
//        - Execute as: Me (info@kidspatch.ie)
//        - Who has access: Anyone
//   6. Click Deploy, authorize the requested Gmail-send permission (it'll
//      warn "Google hasn't verified this app" since it's your own Workspace
//      script -- click Advanced > Go to (project name) to proceed).
//   7. Copy the resulting Web App URL (ends in /exec).
//   8. Paste that URL into APPS_SCRIPT_URL at the top of notify.js in this
//      repo, then commit/push.
//
// To change the email wording later, edit this file, then Deploy > Manage
// deployments > edit (pencil) icon > New version > Deploy -- the URL stays
// the same, so no change needed on the notify.js side.

const ADMIN_EMAIL = 'info@kidspatch.ie';
const SITE_URL = 'https://www.kidspatch.ie';
const SUPABASE_URL = 'https://gnozodfteywsiwcnbwch.supabase.co';

// True only if a claim_requests row with this exact business_id/email/status
// combination really exists -- confirms the payload matches something that
// actually happened in Supabase rather than being fabricated by whoever is
// POSTing to this Web App URL.
function claimRequestExists(businessId, email, status) {
  var key = PropertiesService.getScriptProperties().getProperty('SUPABASE_SERVICE_ROLE_KEY');
  if (!key || !businessId || !email) return false;
  var url = SUPABASE_URL + '/rest/v1/claim_requests'
    + '?business_id=eq.' + encodeURIComponent(businessId)
    + '&requester_email=eq.' + encodeURIComponent(email)
    + '&status=eq.' + encodeURIComponent(status)
    + '&select=id&limit=1';
  var res = UrlFetchApp.fetch(url, {
    headers: { apikey: key, Authorization: 'Bearer ' + key },
    muteHttpExceptions: true,
  });
  if (res.getResponseCode() !== 200) return false;
  var rows = JSON.parse(res.getContentText());
  return rows.length > 0;
}

function doPost(e) {
  try {
    const payload = JSON.parse(e.postData.contents);
    console.log('doPost received type=%s business_id=%s email=%s', payload.type, payload.business_id, payload.requester_email);
    switch (payload.type) {
      case 'new_claim':
        if (claimRequestExists(payload.business_id, payload.requester_email, 'pending')) {
          sendNewClaimEmail(payload);
          console.log('sendNewClaimEmail: sent');
        } else {
          console.log('sendNewClaimEmail: skipped, no matching pending claim_requests row');
        }
        break;
      case 'claim_approved':
        if (claimRequestExists(payload.business_id, payload.requester_email, 'approved')) {
          sendClaimApprovedEmail(payload);
          console.log('sendClaimApprovedEmail: sent');
        } else {
          console.log('sendClaimApprovedEmail: skipped, no matching approved claim_requests row');
        }
        break;
      case 'claim_rejected':
        if (claimRequestExists(payload.business_id, payload.requester_email, 'rejected')) {
          sendClaimRejectedEmail(payload);
          console.log('sendClaimRejectedEmail: sent');
        } else {
          console.log('sendClaimRejectedEmail: skipped, no matching rejected claim_requests row');
        }
        break;
    }
  } catch (err) {
    // Swallow errors -- this endpoint is best-effort (the claim itself is
    // already safely stored in Supabase regardless of whether this email
    // sends), and a thrown error here has no caller listening anyway since
    // the site calls this with fetch(..., {mode: 'no-cors'}).
    console.error('doPost error: ' + err + (err && err.stack ? '\n' + err.stack : ''));
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
