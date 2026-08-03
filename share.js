// Shared "Share" widget for business detail pages (business/*.html, generated
// by scripts/generate_business_pages.py). One static file referenced by every
// generated page rather than inlined per page -- same convention as styles.css.
(function () {
    function fallbackCopy(text) {
        var ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.focus();
        ta.select();
        try { document.execCommand('copy'); } catch (e) { /* ignore */ }
        document.body.removeChild(ta);
    }

    function initShareWidget(wrap) {
        var toggle = wrap.querySelector('.share-toggle');
        var menu = wrap.querySelector('.share-menu');
        if (!toggle || !menu) return;

        var title = menu.dataset.title || document.title;
        var url = menu.dataset.url || window.location.href;

        var waLink = menu.querySelector('[data-share="whatsapp"]');
        var emailLink = menu.querySelector('[data-share="email"]');
        var copyBtn = menu.querySelector('[data-share="copy"]');

        if (waLink) waLink.href = 'https://wa.me/?text=' + encodeURIComponent(title + ' — ' + url);
        if (emailLink) emailLink.href = 'mailto:?subject=' + encodeURIComponent(title) + '&body=' + encodeURIComponent(url);

        function closeMenu() {
            menu.hidden = true;
            toggle.setAttribute('aria-expanded', 'false');
        }
        function openMenu() {
            menu.hidden = false;
            toggle.setAttribute('aria-expanded', 'true');
        }

        toggle.addEventListener('click', function (e) {
            e.stopPropagation();
            if (menu.hidden) openMenu(); else closeMenu();
        });

        document.addEventListener('click', function (e) {
            if (!wrap.contains(e.target)) closeMenu();
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') closeMenu();
        });

        if (copyBtn) {
            copyBtn.addEventListener('click', function () {
                var label = copyBtn.querySelector('.share-copy-label');
                var showCopied = function () {
                    if (label) label.textContent = 'Copied!';
                    copyBtn.classList.add('copied');
                    setTimeout(function () {
                        if (label) label.textContent = 'Copy link';
                        copyBtn.classList.remove('copied');
                    }, 1800);
                };
                if (navigator.clipboard && navigator.clipboard.writeText) {
                    navigator.clipboard.writeText(url).then(showCopied).catch(function () {
                        fallbackCopy(url);
                        showCopied();
                    });
                } else {
                    fallbackCopy(url);
                    showCopied();
                }
                closeMenu();
            });
        }
    }

    function init() {
        document.querySelectorAll('.share-wrap').forEach(initShareWidget);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
