// Map view for category/county/combo landing pages (classes/*.html, generated
// by scripts/generate_landing_pages.py). One shared static file, same
// convention as styles.css/share.js -- pin data is embedded per-page as a
// JSON script tag (#landing-map-data) rather than fetched at runtime, since
// the page already knows its own result set at generation time.
(function () {
    function escapeHtml(s) {
        return String(s || '').replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }

    function init() {
        var container = document.getElementById('landing-map');
        var dataEl = document.getElementById('landing-map-data');
        if (!container || !dataEl || typeof L === 'undefined') return;

        var points;
        try {
            points = JSON.parse(dataEl.textContent);
        } catch (e) {
            return;
        }
        if (!points || !points.length) return;

        var map = L.map('landing-map');
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '&copy; OpenStreetMap',
        }).addTo(map);

        var group = (typeof L.markerClusterGroup === 'function')
            ? L.markerClusterGroup({ maxClusterRadius: 50 })
            : L.layerGroup();

        points.forEach(function (p) {
            var marker = L.marker([p.lat, p.lon]);
            var popup = '<b>' + escapeHtml(p.name) + '</b>';
            if (p.category) popup += '<br>' + escapeHtml(p.category);
            popup += '<br><a href="' + p.url + '">View details &rarr;</a>';
            marker.bindPopup(popup);
            group.addLayer(marker);
        });
        map.addLayer(group);

        if (points.length === 1) {
            map.setView([points[0].lat, points[0].lon], 14);
        } else {
            map.fitBounds(group.getBounds(), { padding: [30, 30] });
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
