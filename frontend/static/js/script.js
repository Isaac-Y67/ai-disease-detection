const CIRCUMFERENCE = 364.42;

function animateGauge(percentage, colorVar) {
    const arc = document.getElementById("gaugeArc");
    const valueEl = document.getElementById("gaugeValue");
    const labelEl = document.getElementById("gaugeLabel");

    // Reset instantly to zero (no transition) before animating up,
    // so repeated submissions always animate from scratch
    arc.style.transition = "none";
    arc.style.strokeDashoffset = CIRCUMFERENCE;
    arc.getBoundingClientRect(); // forces the browser to apply the reset before animating

    arc.style.transition = "";
    arc.style.stroke = colorVar;

    const offset = CIRCUMFERENCE - (percentage / 100) * CIRCUMFERENCE;
    requestAnimationFrame(() => {
        arc.style.strokeDashoffset = offset;
    });

    // Count the number up in sync with the arc animation
    const duration = 1100;
    const startTime = performance.now();

    function step(now) {
        const progress = Math.min((now - startTime) / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
        valueEl.textContent = (eased * percentage).toFixed(1) + "%";
        if (progress < 1) {
            requestAnimationFrame(step);
        } else {
            valueEl.textContent = percentage.toFixed(1) + "%";
        }
    }
    requestAnimationFrame(step);

    labelEl.textContent = "likelihood of disease";
}

document.getElementById("predictionForm").addEventListener("submit", async function (e) {
    e.preventDefault();

    const formData = new FormData(this);
    const data = {};
    formData.forEach((value, key) => {
        data[key] = parseFloat(value);
    });

    const resultEmpty = document.getElementById("resultEmpty");
    const resultFilled = document.getElementById("resultFilled");
    const statusLine = document.getElementById("statusLine");

    resultEmpty.classList.add("is-hidden");
    resultFilled.classList.remove("is-hidden");
    statusLine.textContent = "Analyzing…";
    statusLine.className = "status-line";

    try {
        const response = await fetch("/predict", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (result.error) {
            statusLine.textContent = "Error: " + result.error;
            statusLine.className = "status-line status-positive";
            return;
        }

        const riskColors = {
            High: "var(--danger)",
            Moderate: "var(--warning)",
            Low: "var(--safe)"
        };

        const percentage = result.probability * 100;
        animateGauge(percentage, riskColors[result.risk_level] || "var(--accent)");

        const statusClass = result.disease_detected ? "status-positive" : "status-negative";
        const statusText = result.disease_detected
            ? `Disease indicators detected — ${result.risk_level} risk`
            : `No disease indicators detected — ${result.risk_level} risk`;

        statusLine.textContent = statusText;
        statusLine.className = "status-line " + statusClass;

    } catch (err) {
        statusLine.textContent = "Something went wrong. Please try again.";
        statusLine.className = "status-line status-positive";
    }
});