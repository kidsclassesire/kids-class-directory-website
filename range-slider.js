// Dual-handle range slider (Age/Price filters). Two overlapping <input type=range>
// is the standard dependency-free way to get this: pointer-events is disabled on
// the input itself (CSS) and re-enabled only on the ::-webkit-slider-thumb/
// ::-moz-range-thumb, so each handle stays independently draggable regardless of
// DOM order or z-index. Shared by landing-filters.js (category/county/combo pages)
// and index.html (main search) -- same markup/CSS classes (.range-slider,
// .range-track, .range-track-fill, see styles.css) either way.
function setupRangeSlider(container, onChange, onCommit) {
    var minInput = container.querySelector('input:first-of-type');
    var maxInput = container.querySelector('input:last-of-type');
    var fill = container.querySelector('.range-track-fill');
    var rangeMin = parseFloat(minInput.min);
    var rangeMax = parseFloat(minInput.max);

    function paintFill(minVal, maxVal) {
        var pctMin = ((minVal - rangeMin) / (rangeMax - rangeMin)) * 100;
        var pctMax = ((maxVal - rangeMin) / (rangeMax - rangeMin)) * 100;
        fill.style.left = pctMin + '%';
        fill.style.right = (100 - pctMax) + '%';
    }

    function update() {
        var minVal = parseFloat(minInput.value);
        var maxVal = parseFloat(maxInput.value);
        if (minVal > maxVal) {
            if (document.activeElement === maxInput) {
                minVal = maxVal;
                minInput.value = String(minVal);
            } else {
                maxVal = minVal;
                maxInput.value = String(maxVal);
            }
        }
        paintFill(minVal, maxVal);
        onChange(minVal, maxVal, rangeMin, rangeMax);
    }

    minInput.addEventListener('input', update);
    maxInput.addEventListener('input', update);
    // 'change' (not 'input') fires once on release/keyup rather than on every drag
    // tick, so this is where analytics tracking hooks in -- an 'input'-driven
    // trackEvent call would spam GA with a call per pixel of drag.
    if (onCommit) {
        minInput.addEventListener('change', onCommit);
        maxInput.addEventListener('change', onCommit);
    }
    // Paint-only, deliberately not calling update()/onChange() here: at
    // construction time the caller's own `var xSlider = setupRangeSlider(...)`
    // assignment hasn't completed yet, so a callback that reads that variable
    // would blow up on the very first slider set up this way. Callers trigger the
    // real initial state explicitly once every slider they need exists instead.
    paintFill(rangeMin, rangeMax);

    return {
        bounds: { min: rangeMin, max: rangeMax },
        reset: function () {
            minInput.value = String(rangeMin);
            maxInput.value = String(rangeMax);
            paintFill(rangeMin, rangeMax);
        },
        // Programmatically position both handles (e.g. restoring from a URL param) --
        // does not fire onChange itself, so callers update their own state after.
        set: function (minVal, maxVal) {
            minInput.value = String(minVal);
            maxInput.value = String(maxVal);
            paintFill(minVal, maxVal);
        },
    };
}
