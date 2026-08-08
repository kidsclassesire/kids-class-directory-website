// Fire-and-forget claim-flow email notifications, sent via a Google Apps
// Script Web App (see gmail_notifications.gs) that emails from a real Gmail
// account -- no backend, no third-party email service. One shared static
// file, same convention as analytics.js/share.js.
//
// APPS_SCRIPT_URL points at the deployed Web App from gmail_notifications.gs
// (running under info@kidspatch.ie) -- if it's ever redeployed as a new
// project the URL changes and this needs updating, but redeploying an
// existing project as a new *version* (Deploy > Manage deployments > edit >
// New version) keeps the same URL, so that path needs no change here.
(function () {
    var APPS_SCRIPT_URL = 'https://script.google.com/macros/s/AKfycbwNfGviSwkLdnBv-3V2kKXr-GyAzS4JmuHHYWxLekXseUhvdGITjs5IaR1rvbNOUg-z/exec';

    function send(type, payload) {
        if (!APPS_SCRIPT_URL) return;
        try {
            fetch(APPS_SCRIPT_URL, {
                method: 'POST',
                mode: 'no-cors',
                body: JSON.stringify(Object.assign({ type: type }, payload)),
            });
        } catch (e) {
            // best-effort only
        }
    }

    window.notifyClaim = function (type, payload) {
        send(type, payload);
    };

    // "Request Info" form (enquiry.js) -- like notifyClaim, the Apps Script
    // side re-verifies this against the matching enquiries row in Supabase
    // (by id) before it will actually send mail, since this endpoint is
    // public and anyone can POST to it directly.
    window.notifyEnquiry = function (payload) {
        send('new_enquiry', payload);
    };

    // Contact form (contact.html) -- unlike notifyClaim, there's no Supabase
    // row for the Apps Script side to verify this against, since a contact
    // message isn't stored anywhere; it only ever emails ADMIN_EMAIL itself
    // (never the sender), so that's an acceptable amount of open-relay
    // exposure for this one message type.
    window.notifyContact = function (payload) {
        send('contact', payload);
    };
})();
