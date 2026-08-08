// Shared "Request Info" / "Message Provider" modal + form logic, used by
// index.html and every generated business page (same convention as
// claim.js/styles.css/share.js). Both page types ship the same modal markup
// (id="enquiry-modal" etc.) and this file's job is purely behavior --
// open/close, honeypot spam filtering, and the actual submit.
(function () {
    function els() {
        return {
            modal: document.getElementById('enquiry-modal'),
            closeBtn: document.getElementById('close-enquiry-modal'),
            title: document.getElementById('enquiry-modal-business-name'),
            form: document.getElementById('enquiry-form'),
            businessId: document.getElementById('enquiry-business-id'),
            businessTitle: document.getElementById('enquiry-business-title'),
            submitBtn: document.getElementById('enquiry-submit'),
            success: document.getElementById('enquiry-success'),
            honeypot: document.getElementById('enquiry-hp'),
        };
    }

    window.openEnquiryModal = function (businessId, businessName) {
        var e = els();
        if (!e.modal) return;

        e.title.textContent = 'Message ' + businessName;
        e.form.reset();
        e.businessId.value = businessId;
        e.businessTitle.value = businessName;
        e.form.style.display = 'block';
        e.success.style.display = 'none';
        e.modal.classList.add('active');

        if (typeof window.trackEvent === 'function') {
            window.trackEvent('enquiry_started', { business_id: businessId, business_name: businessName });
        }
    };

    function closeModal() {
        var e = els();
        if (e.modal) e.modal.classList.remove('active');
    }

    // Correlates this submission with the notify.js fetch below without
    // needing to read the row back after insert -- enquiries' SELECT policy
    // deliberately doesn't allow the anonymous submitter to do that (see
    // add_enquiries_table.sql), only the business's owner/admin.
    function makeToken() {
        if (window.crypto && window.crypto.randomUUID) return window.crypto.randomUUID();
        return 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'.replace(/x/g, function () {
            return Math.floor(Math.random() * 16).toString(16);
        });
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

            e.submitBtn.textContent = 'Sending...';
            e.submitBtn.disabled = true;

            var requestData = {
                business_id: e.businessId.value,
                business_name: e.businessTitle.value,
                parent_name: document.getElementById('enquiry-name').value.trim(),
                parent_email: document.getElementById('enquiry-email').value.trim().toLowerCase(),
                parent_phone: document.getElementById('enquiry-phone').value.trim(),
                message: document.getElementById('enquiry-message').value.trim(),
                token: makeToken(),
            };

            try {
                var client = window.supabaseClient;
                var res = await client.from('enquiries').insert([requestData]);
                if (res.error) throw res.error;

                e.form.style.display = 'none';
                e.success.style.display = 'block';
                document.getElementById('enquiry-success-business-name').textContent = requestData.business_name;

                if (typeof window.trackEvent === 'function') {
                    window.trackEvent('enquiry_submitted', { business_id: requestData.business_id, business_name: requestData.business_name });
                }
                if (typeof window.notifyEnquiry === 'function') {
                    window.notifyEnquiry(requestData);
                }
            } catch (err) {
                alert('There was an error sending your message. Please check your connection and try again.');
                console.error(err);
            } finally {
                e.submitBtn.textContent = 'Send Message';
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
