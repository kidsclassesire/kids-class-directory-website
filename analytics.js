// Shared GA4 event-tracking helpers, used by index.html and every generated
// business/landing page (same convention as styles.css/share.js). Kept as
// two tiny globals rather than a bundled module since every page here is a
// plain <script> context, not an ES module graph.
(function () {
    // Wraps gtag('event', ...) so a tracking call is never the thing that
    // breaks a real feature -- if GA failed to load (ad blocker, network
    // issue, whatever), this is a silent no-op instead of a thrown error.
    window.trackEvent = function (name, params) {
        if (typeof window.gtag === 'function') {
            window.gtag('event', name, params || {});
        }
    };

    // Tags an outbound URL with utm_source=kidspatch so a business owner can
    // see in their own analytics that a click came from the directory --
    // separate from (and complementary to) our own outbound_click GA event.
    window.withUtm = function (rawUrl, medium) {
        if (!rawUrl) return rawUrl;
        try {
            var u = new URL(rawUrl, window.location.href);
            u.searchParams.set('utm_source', 'kidspatch');
            u.searchParams.set('utm_medium', medium || 'referral');
            return u.toString();
        } catch (e) {
            return rawUrl;
        }
    };
})();
