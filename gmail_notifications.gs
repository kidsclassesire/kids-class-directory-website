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
// To change the email wording or styling later, edit this file, then
// Deploy > Manage deployments > edit (pencil) icon > New version > Deploy --
// the URL stays the same, so no change needed on the notify.js side.

const ADMIN_EMAIL = 'info@kidspatch.ie';
const SITE_URL = 'https://www.kidspatch.ie';
const SUPABASE_URL = 'https://gnozodfteywsiwcnbwch.supabase.co';
// GmailApp.sendEmail's `name` option -- without it, every email shows up in
// the recipient's inbox as coming from the raw address (info@kidspatch.ie)
// rather than a friendly sender name.
const SENDER_NAME = 'Kids Patch';

// Mirrors the palette in styles.css (:root) so the emails look like the
// same product as the website rather than a generic notification.
const BRAND = {
  primary: '#FF7A5C',
  secondary: '#0F6E6E',
  accent: '#FFC857',
  textDark: '#212B2B',
  textMuted: '#5C6B6B',
  bgPage: '#FAF9F6',
  border: '#DCE3E3',
};

// The site's real app icon (teal square, "K", yellow dot) -- already
// deployed and cacheable, so no extra asset to host just for emails.
const LOGO_URL = SITE_URL + '/apple-touch-icon.png';

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

// Used to decide whether sendEnquiryEmail's "claim your listing" pitch is
// worth showing -- no point pitching an owner who already has portal access.
function isBusinessClaimed(businessId) {
  var key = PropertiesService.getScriptProperties().getProperty('SUPABASE_SERVICE_ROLE_KEY');
  if (!key || !businessId) return false;
  var url = SUPABASE_URL + '/rest/v1/claim_requests'
    + '?business_id=eq.' + encodeURIComponent(businessId)
    + '&status=eq.approved'
    + '&select=id&limit=1';
  var res = UrlFetchApp.fetch(url, {
    headers: { apikey: key, Authorization: 'Bearer ' + key },
    muteHttpExceptions: true,
  });
  if (res.getResponseCode() !== 200) return false;
  var rows = JSON.parse(res.getContentText());
  return rows.length > 0;
}

// True only if an enquiries row with this exact token/business_id/parent_email
// exists and hasn't been emailed yet (notified=false) -- confirms the
// payload matches a real "Request Info" submission rather than being
// fabricated by whoever is POSTing to this Web App URL, and stops a
// replayed POST of the same token from re-emailing the business. Matched on
// the client-generated token (not the row's id) because the anonymous
// submitter's insert can't read the row's id back -- see the `token` column
// comment in add_enquiries_table.sql.
function enquiryRequestExists(token, businessId, parentEmail) {
  var key = PropertiesService.getScriptProperties().getProperty('SUPABASE_SERVICE_ROLE_KEY');
  if (!key || !token || !businessId || !parentEmail) return false;
  var url = SUPABASE_URL + '/rest/v1/enquiries'
    + '?token=eq.' + encodeURIComponent(token)
    + '&business_id=eq.' + encodeURIComponent(businessId)
    + '&parent_email=eq.' + encodeURIComponent(parentEmail)
    + '&notified=eq.false'
    + '&select=id&limit=1';
  var res = UrlFetchApp.fetch(url, {
    headers: { apikey: key, Authorization: 'Bearer ' + key },
    muteHttpExceptions: true,
  });
  if (res.getResponseCode() !== 200) return false;
  var rows = JSON.parse(res.getContentText());
  return rows.length > 0;
}

function markEnquiryNotified(token) {
  var key = PropertiesService.getScriptProperties().getProperty('SUPABASE_SERVICE_ROLE_KEY');
  if (!key || !token) return;
  var url = SUPABASE_URL + '/rest/v1/enquiries?token=eq.' + encodeURIComponent(token);
  UrlFetchApp.fetch(url, {
    method: 'patch',
    headers: { apikey: key, Authorization: 'Bearer ' + key, 'Content-Type': 'application/json', Prefer: 'return=minimal' },
    payload: JSON.stringify({ notified: true }),
    muteHttpExceptions: true,
  });
}

// The enquiry payload's business_name/business_id come from the page the
// visitor was on, not from a source we control server-side, so the actual
// send-to address is looked up fresh from `classes` here rather than trusted
// from the client -- otherwise the public Web App URL would let anyone make
// info@kidspatch.ie email an arbitrary address of their choosing.
function getBusinessContact(businessId) {
  var key = PropertiesService.getScriptProperties().getProperty('SUPABASE_SERVICE_ROLE_KEY');
  if (!key || !businessId) return null;
  var url = SUPABASE_URL + '/rest/v1/classes'
    + '?id=eq.' + encodeURIComponent(businessId)
    + '&select=company_name,email_address&limit=1';
  var res = UrlFetchApp.fetch(url, {
    headers: { apikey: key, Authorization: 'Bearer ' + key },
    muteHttpExceptions: true,
  });
  if (res.getResponseCode() !== 200) return null;
  var rows = JSON.parse(res.getContentText());
  return rows.length > 0 ? rows[0] : null;
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
      case 'contact':
        sendContactEmail(payload);
        console.log('sendContactEmail: sent');
        break;
      case 'new_enquiry':
        if (enquiryRequestExists(payload.token, payload.business_id, payload.parent_email)) {
          var business = getBusinessContact(payload.business_id);
          if (business && business.email_address) {
            sendEnquiryEmail(payload, business, isBusinessClaimed(payload.business_id));
            sendEnquiryConfirmationEmail(payload, business);
            console.log('sendEnquiryEmail: sent');
          } else {
            console.log('sendEnquiryEmail: skipped, business has no email_address on file');
          }
          markEnquiryNotified(payload.token);
        } else {
          console.log('sendEnquiryEmail: skipped, no matching un-notified enquiries row');
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

// ---------------------------------------------------------------------
// HTML email template helpers
//
// Deliberately old-school table-based markup with inline styles rather
// than a <style> block or flexbox/grid -- Gmail/Outlook/Apple Mail strip
// or mis-render modern CSS in HTML email, but this subset is reliably
// supported everywhere. All user-supplied fields are escaped since this
// endpoint is public (see claimRequestExists() note above) and the
// contact form message is free text -- unescaped values could otherwise
// break the layout or inject markup into an email sent from our account.
// ---------------------------------------------------------------------

function escapeHtml(str) {
  return String(str == null ? '' : str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function nl2br(str) {
  return escapeHtml(str).replace(/\n/g, '<br>');
}

function firstName(name) {
  var n = (name || '').toString().trim();
  return n ? n.split(/\s+/)[0] : 'there';
}

// rows: array of [label, value] pairs; blank values are skipped.
function detailBox(rows) {
  var cells = rows
    .filter(function (r) { return r[1]; })
    .map(function (r) {
      return '<tr>'
        + '<td style="padding:5px 0; font-family:Helvetica,Arial,sans-serif; font-size:13px; color:' + BRAND.textMuted + '; white-space:nowrap; vertical-align:top; padding-right:12px;">' + escapeHtml(r[0]) + '</td>'
        + '<td style="padding:5px 0; font-family:Helvetica,Arial,sans-serif; font-size:14px; color:' + BRAND.textDark + '; vertical-align:top;">' + r[1] + '</td>'
        + '</tr>';
    })
    .join('');
  if (!cells) return '';
  return '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:' + BRAND.bgPage + '; border:1px solid ' + BRAND.border + '; border-radius:8px; margin:20px 0;">'
    + '<tr><td style="padding:14px 16px;">'
    + '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">' + cells + '</table>'
    + '</td></tr></table>';
}

// opts: { preheader, heading, bodyHtml, cta: {label, url} | null }
function emailShell(opts) {
  var cta = '';
  if (opts.cta) {
    cta = '<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:28px auto 4px;">'
      + '<tr><td align="center" bgcolor="' + BRAND.primary + '" style="border-radius:8px;">'
      + '<a href="' + opts.cta.url + '" target="_blank" style="display:inline-block; padding:14px 32px; font-family:Helvetica,Arial,sans-serif; font-size:15px; font-weight:bold; color:#ffffff; text-decoration:none; border-radius:8px;">' + escapeHtml(opts.cta.label) + '</a>'
      + '</td></tr></table>';
  }

  return '<!DOCTYPE html><html><head><meta charset="utf-8">'
    + '<meta name="viewport" content="width=device-width, initial-scale=1.0"></head>'
    + '<body style="margin:0; padding:0; background-color:' + BRAND.bgPage + ';">'
    + '<div style="display:none; max-height:0; overflow:hidden; opacity:0;">' + escapeHtml(opts.preheader || '') + '</div>'
    + '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:' + BRAND.bgPage + ';"><tr><td align="center" style="padding:32px 16px;">'
    + '<table role="presentation" width="480" cellpadding="0" cellspacing="0" border="0" style="max-width:480px; width:100%; background-color:#ffffff; border-radius:12px; overflow:hidden; border:1px solid ' + BRAND.border + ';">'
    + '<tr><td bgcolor="' + BRAND.secondary + '" style="padding:20px 28px;">'
    + '<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>'
    + '<td style="padding-right:10px;"><img src="' + LOGO_URL + '" width="32" height="32" alt="" style="display:block; border-radius:7px;"></td>'
    + '<td style="font-family:Helvetica,Arial,sans-serif; font-size:18px; font-weight:bold; color:#ffffff; letter-spacing:0.2px;">Kids Patch</td>'
    + '</tr></table></td></tr>'
    + '<tr><td style="padding:32px 28px 28px;">'
    + '<h1 style="margin:0 0 16px; font-family:Helvetica,Arial,sans-serif; font-size:20px; line-height:1.3; color:' + BRAND.textDark + ';">' + opts.heading + '</h1>'
    + '<div style="font-family:Helvetica,Arial,sans-serif; font-size:15px; line-height:1.65; color:' + BRAND.textDark + ';">' + opts.bodyHtml + '</div>'
    + cta
    + '</td></tr>'
    + '<tr><td bgcolor="' + BRAND.accent + '" style="height:4px; line-height:4px; font-size:0;">&nbsp;</td></tr>'
    + '</table>'
    + '<table role="presentation" width="480" cellpadding="0" cellspacing="0" border="0" style="max-width:480px; width:100%;"><tr>'
    + '<td align="center" style="padding:20px 16px 0; font-family:Helvetica,Arial,sans-serif; font-size:12px; line-height:1.6; color:' + BRAND.textMuted + ';">'
    + 'Kids Patch &middot; <a href="' + SITE_URL + '" style="color:' + BRAND.secondary + '; text-decoration:none;">kidspatch.ie</a><br>'
    + "Ireland's directory of kids' classes &amp; activities"
    + '</td></tr></table>'
    + '</td></tr></table></body></html>';
}

// ---------------------------------------------------------------------
// Emails
// ---------------------------------------------------------------------

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

  const bodyHtml = '<p style="margin:0;">A new &ldquo;claim this business&rdquo; request just came in on Kids Patch.</p>'
    + detailBox([
      ['Business', escapeHtml(p.business_name || '') + (p.business_id ? ' <span style="color:' + BRAND.textMuted + ';">(ID: ' + escapeHtml(p.business_id) + ')</span>' : '')],
      ['Requester', escapeHtml(p.requester_name || '') + (p.requester_position ? ' &mdash; ' + escapeHtml(p.requester_position) : '')],
      ['Email', escapeHtml(p.requester_email || '')],
    ]);

  const htmlBody = emailShell({
    preheader: `New claim request for ${p.business_name || 'a business'}`,
    heading: 'New claim request',
    bodyHtml: bodyHtml,
    cta: { label: 'Review in admin panel', url: SITE_URL + '/admin.html' },
  });

  GmailApp.sendEmail(ADMIN_EMAIL, subject, body, { htmlBody: htmlBody, name: SENDER_NAME });
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

  const bodyHtml = '<p style="margin:0 0 12px;">Hi ' + escapeHtml(firstName(p.requester_name)) + ',</p>'
    + '<p style="margin:0 0 12px;">Good news &mdash; your claim for <strong>' + escapeHtml(p.business_name || 'your business') + '</strong> on Kids Patch has been approved.</p>'
    + '<p style="margin:0;">You can now manage your listing &mdash; update details, photos and class information any time.</p>'
    + detailBox([['Log in with', escapeHtml(p.requester_email)]]);

  const htmlBody = emailShell({
    preheader: `Your claim for ${p.business_name || 'your business'} was approved`,
    heading: 'Your claim was approved',
    bodyHtml: bodyHtml,
    cta: { label: 'Manage your listing', url: SITE_URL + '/portal.html' },
  });

  GmailApp.sendEmail(p.requester_email, subject, body, { htmlBody: htmlBody, name: SENDER_NAME });
}

// The core "prove we send you customers" email -- goes straight to the
// business's own listed address with replyTo set to the parent, so the
// owner can just hit reply to respond, no Kids Patch account needed. That's
// deliberate: the value pitch to a not-yet-signed-up business is "look, a
// real enquiry landed in your inbox," not "come use our tools."
function sendEnquiryEmail(p, business, alreadyClaimed) {
  const name = business.company_name || p.business_name || 'your listing';
  const subject = `New enquiry via Kids Patch: ${name}`;

  // Only pitched at businesses that haven't claimed their listing yet -- an
  // owner who already has portal access doesn't need convincing, and
  // repeating the pitch on every enquiry would just get noisy for them.
  const claimPitchText = alreadyClaimed ? '' : [
    ``,
    `This enquiry came from your free Kids Patch listing -- a directory Irish parents use to find kids' classes and activities. You haven't claimed your listing yet, which means you can't update your own details, photos or schedule, or see how many parents are viewing your page.`,
    ``,
    `Claiming it takes a minute and is free: ${SITE_URL}/portal.html`,
  ].join('\n');

  const body = [
    `You have a new enquiry via Kids Patch for "${name}".`,
    ``,
    `From: ${p.parent_name || ''} (${p.parent_email || ''})`,
    p.parent_phone ? `Phone: ${p.parent_phone}` : null,
    ``,
    `Message:`,
    p.message || '',
    ``,
    `Reply directly to this email to respond to ${firstName(p.parent_name)}.`,
    claimPitchText || null,
  ].filter(function (line) { return line !== null; }).join('\n');

  const claimPitchHtml = alreadyClaimed ? '' : (
    '<div style="margin-top:20px; padding-top:16px; border-top:1px solid ' + BRAND.border + '; font-size:13.5px; line-height:1.6; color:' + BRAND.textMuted + ';">'
    + 'This enquiry came from your free Kids Patch listing &mdash; a directory Irish parents use to find kids&rsquo; classes and activities. You haven&rsquo;t claimed your listing yet, which means you can&rsquo;t update your own details, photos or schedule, or see how many parents are viewing your page. Claiming it takes a minute and is free.'
    + '</div>'
  );

  const bodyHtml = '<p style="margin:0 0 12px;">You have a new enquiry via Kids Patch for <strong>' + escapeHtml(name) + '</strong>.</p>'
    + detailBox([
      ['From', escapeHtml(p.parent_name || '') + ' &lt;' + escapeHtml(p.parent_email || '') + '&gt;'],
      ['Phone', escapeHtml(p.parent_phone || '')],
    ])
    + '<div style="margin-top:4px; padding:14px 16px; border-left:3px solid ' + BRAND.accent + '; background-color:' + BRAND.bgPage + '; border-radius:0 8px 8px 0; font-size:15px; line-height:1.6; color:' + BRAND.textDark + ';">' + nl2br(p.message || '') + '</div>'
    + '<p style="margin:16px 0 0; font-size:13px; color:' + BRAND.textMuted + ';">Just reply to this email to respond to ' + escapeHtml(firstName(p.parent_name)) + ' directly.</p>'
    + claimPitchHtml;

  const htmlBody = emailShell({
    preheader: `New enquiry from ${p.parent_name || 'a parent'} via Kids Patch`,
    heading: 'You have a new enquiry',
    bodyHtml: bodyHtml,
    cta: alreadyClaimed ? null : { label: 'Claim your free listing', url: SITE_URL + '/portal.html' },
  });

  var options = { htmlBody: htmlBody, name: SENDER_NAME };
  if (p.parent_email) options.replyTo = p.parent_email;
  GmailApp.sendEmail(business.email_address, subject, body, options);
}

// Closes the loop for the parent so they're not left wondering whether their
// message actually went anywhere -- mirrors sendClaimApprovedEmail's tone.
function sendEnquiryConfirmationEmail(p, business) {
  if (!p.parent_email) return;
  const name = business.company_name || p.business_name || 'the business';
  const subject = `Your message to ${name} has been sent`;
  const body = [
    `Hi ${firstName(p.parent_name)},`,
    ``,
    `Your message to "${name}" has been sent via Kids Patch. They'll be in touch directly using the contact details you gave.`,
    ``,
    `-- Kids Patch`,
  ].join('\n');

  const bodyHtml = '<p style="margin:0 0 12px;">Hi ' + escapeHtml(firstName(p.parent_name)) + ',</p>'
    + '<p style="margin:0;">Your message to <strong>' + escapeHtml(name) + '</strong> has been sent. They\'ll be in touch directly using the contact details you gave.</p>';

  const htmlBody = emailShell({
    preheader: `Your message to ${name} has been sent`,
    heading: 'Message sent',
    bodyHtml: bodyHtml,
    cta: null,
  });

  GmailApp.sendEmail(p.parent_email, subject, body, { htmlBody: htmlBody, name: SENDER_NAME });
}

// Unlike the claim emails above, this has no claim_requests row to verify
// against -- it's the contact form's own free-text message, and it always
// goes to ADMIN_EMAIL (never the sender), so there's no arbitrary-recipient
// open-relay risk to gate against here, just plain spam, which relies on
// contact.html's honeypot field to filter.
function sendContactEmail(p) {
  var message = (p.message || '').toString().trim();
  if (!message) return;
  var subject = `Kids Patch contact form: ${(p.subject || '').toString().trim() || 'New message'}`;
  var body = [
    `New message from the Kids Patch contact form.`,
    ``,
    `Name: ${p.name || ''}`,
    `Email: ${p.email || ''}`,
    ``,
    message,
  ].join('\n');

  var bodyHtml = detailBox([
    ['Name', escapeHtml(p.name || '')],
    ['Email', escapeHtml(p.email || '')],
    ['Subject', escapeHtml((p.subject || '').toString().trim())],
  ])
    + '<div style="margin-top:4px; padding:14px 16px; border-left:3px solid ' + BRAND.accent + '; background-color:' + BRAND.bgPage + '; border-radius:0 8px 8px 0; font-size:15px; line-height:1.6; color:' + BRAND.textDark + ';">' + nl2br(message) + '</div>';

  var htmlBody = emailShell({
    preheader: 'New message from the Kids Patch contact form',
    heading: 'New contact form message',
    bodyHtml: bodyHtml,
    cta: null,
  });

  var options = { htmlBody: htmlBody, name: SENDER_NAME };
  if (p.email) options.replyTo = p.email;
  GmailApp.sendEmail(ADMIN_EMAIL, subject, body, options);
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

  const bodyHtml = '<p style="margin:0 0 12px;">Hi ' + escapeHtml(firstName(p.requester_name)) + ',</p>'
    + '<p style="margin:0 0 12px;">Thanks for your interest in claiming <strong>' + escapeHtml(p.business_name || 'this business') + '</strong> on Kids Patch.</p>'
    + '<p style="margin:0 0 12px;">We weren\'t able to verify this claim, so it hasn\'t been approved.</p>'
    + '<p style="margin:0;">If you believe this is a mistake, just reply to this email and we\'ll take another look.</p>';

  const htmlBody = emailShell({
    preheader: `An update on your claim for ${p.business_name || 'your business'}`,
    heading: 'Update on your claim',
    bodyHtml: bodyHtml,
    cta: null,
  });

  GmailApp.sendEmail(p.requester_email, subject, body, { htmlBody: htmlBody, name: SENDER_NAME });
}
