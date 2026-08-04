// Shared "claim this business" modal + form logic, used by index.html and
// every generated business page (same convention as styles.css/share.js).
// Both page types ship the same modal markup (id="claim-modal" etc.) and
// this file's job is purely behavior -- open/close, an "already claimed?"
// check, honeypot spam filtering, and the actual submit.
(function () {
    function els() {
        return {
            modal: document.getElementById('claim-modal'),
            closeBtn: document.getElementById('close-modal'),
            title: document.getElementById('modal-business-name'),
            form: document.getElementById('claim-form'),
            businessId: document.getElementById('claim-business-id'),
            businessTitle: document.getElementById('claim-business-title'),
            submitBtn: document.getElementById('claim-submit'),
            success: document.getElementById('claim-success'),
            loading: document.getElementById('claim-loading'),
            already: document.getElementById('claim-already'),
            honeypot: document.getElementById('claim-hp'),
        };
    }

    // Best-effort "does this business already have an open claim" check --
    // fails open (shows the form) on any error, since this is a UX nicety on
    // top of admin review, not the actual security boundary.
    async function checkClaimStatus(businessId) {
        var e = els();
        try {
            var client = window.supabaseClient;
            var res = await client.rpc('claim_status_for_business', { p_business_id: String(businessId) });
            e.loading.style.display = 'none';
            if (res.data === 'approved' || res.data === 'pending') {
                e.already.textContent = res.data === 'approved'
                    ? 'This business has already been claimed and verified.'
                    : 'This business already has a claim under review.';
                e.already.style.display = 'block';
            } else {
                e.form.style.display = 'block';
            }
        } catch (err) {
            e.loading.style.display = 'none';
            e.form.style.display = 'block';
        }
    }

    window.openClaimModal = function (businessId, businessName) {
        var e = els();
        if (!e.modal) return;

        e.businessId.value = businessId;
        e.businessTitle.value = businessName;
        e.title.textContent = 'Claim ' + businessName;
        e.form.reset();
        e.form.style.display = 'none';
        e.success.style.display = 'none';
        e.already.style.display = 'none';
        e.loading.style.display = 'block';
        e.modal.classList.add('active');

        if (typeof window.trackEvent === 'function') {
            window.trackEvent('claim_started', { business_id: businessId, business_name: businessName });
        }
        checkClaimStatus(businessId);
    };

    function closeModal() {
        var e = els();
        if (e.modal) e.modal.classList.remove('active');
    }

    function init() {
        var e = els();
        if (!e.modal) return;

        if (e.closeBtn) e.closeBtn.addEventListener('click', closeModal);
        e.modal.addEventListener('click', function (ev) { if (ev.target === e.modal) closeModal(); });

        e.form.addEventListener('submit', async function (ev) {
            ev.preventDefault();

            // Honeypot: a real visitor never sees or fills this field (it's
            // positioned off-screen); a form-filling bot typically does.
            if (e.honeypot && e.honeypot.value) return;

            e.submitBtn.textContent = 'Submitting...';
            e.submitBtn.disabled = true;

            var requestData = {
                business_id: e.businessId.value,
                business_name: e.businessTitle.value,
                requester_name: document.getElementById('claim-name').value.trim(),
                requester_email: document.getElementById('claim-email').value.trim().toLowerCase(),
                requester_position: document.getElementById('claim-position').value.trim(),
                status: 'pending',
            };

            try {
                var client = window.supabaseClient;
                var res = await client.from('claim_requests').insert([requestData]);
                if (res.error) throw res.error;

                e.form.style.display = 'none';
                e.success.style.display = 'block';

                if (typeof window.trackEvent === 'function') {
                    window.trackEvent('claim_submitted', { business_id: requestData.business_id, business_name: requestData.business_name });
                }
                if (typeof window.notifyClaim === 'function') {
                    window.notifyClaim('new_claim', requestData);
                }
            } catch (err) {
                alert('There was an error submitting your claim. Please check your connection and try again.');
                console.error(err);
            } finally {
                e.submitBtn.textContent = 'Submit Claim Request';
                e.submitBtn.disabled = false;
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
