// Fire-and-forget claim-flow email notifications, sent via a Google Apps
// Script Web App (see gmail_notifications.gs) that emails from a real Gmail
// account -- no backend, no third-party email service. One shared static
// file, same convention as analytics.js/share.js.
//
// APPS_SCRIPT_URL is blank until gmail_notifications.gs is deployed (see the
// setup steps at the top of that file) -- until then, notifyClaim() is a
// silent no-op, same "never break the real feature" philosophy as
// trackEvent() in analytics.js. The claim itself is already safely stored in
// Supabase regardless of whether this email sends.
(function () {
    var APPS_SCRIPT_URL = '';

    window.notifyClaim = function (type, payload) {
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
    };
})();
