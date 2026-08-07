// Canonical category / facility / day-of-week lists shared by index.html,
// portal.html, and admin.html. Edit here only -- these used to be hardcoded
// independently in each page (portal.html even carried a comment flagging
// the manual-sync risk), which meant a change made in one place silently
// didn't apply to the others.
//
// Loaded as a plain (non-module, non-deferred) classic script, placed before
// each page's own inline <script> -- top-level `const`/`function` here are
// visible as bare identifiers in that later inline script, same as if they'd
// been declared directly in it, as long as this tag runs first.

const CATEGORY_GROUPS = [
    ['Sports & Fitness', ['Athletics', 'Basketball', 'Football', 'GAA', 'Gymnastics', 'Hockey',
        'Horse Riding', 'Martial Arts', 'Rugby', 'Sports', 'Swimming', 'Team Sports', 'Tennis', 'Watersports']],
    ['Arts, Music & Drama', ['Arts and crafts', 'Cooking', 'Dance', 'Drama', 'Music']],
    ['Baby & Toddler', ['Developmental', 'Parent-and-toddler']],
    ['Academic & STEM', ['Academic Support', 'Languages', 'STEM']],
    ['Camps & Outdoor', ['Camps', 'Outdoor']],
];

const FACILITIES_LIST = [
    'Indoor Venue', 'Outdoor Venue', 'Wheelchair Accessible', 'Buggy Accessible',
    'Cafe On-site', 'Changing Facilities', 'Free Parking', 'Paid Parking', 'Parent Viewing Area',
];

const DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

// Renders `values` as a set of `<label><input type="checkbox">...</label>`
// rows into the given container -- used by portal.html/admin.html for the
// Facilities and Days of the Week checkbox grids, so those options come from
// FACILITIES_LIST/DAYS_OF_WEEK above instead of being retyped as HTML.
function renderCheckboxGridOptions(containerId, values) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = values.map(v =>
        `<label><input type="checkbox" value="${v.replace(/"/g, '&quot;')}"> ${v}</label>`
    ).join('');
}
