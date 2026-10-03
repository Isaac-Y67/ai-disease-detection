const CIRCUMFERENCE = 364.42;

function animateGauge(container, percentage, colorVar) {
    const arc = container.querySelector("#gaugeArc");
    const valueEl = container.querySelector("#gaugeValue");
    const labelEl = container.querySelector("#gaugeLabel");

    arc.style.transition = "none";
    arc.style.strokeDashoffset = CIRCUMFERENCE;
    arc.getBoundingClientRect();

    arc.style.transition = "";
    arc.style.stroke = colorVar;

    const offset = CIRCUMFERENCE - (percentage / 100) * CIRCUMFERENCE;
    requestAnimationFrame(() => {
        arc.style.strokeDashoffset = offset;
    });

    const duration = 1100;
    const startTime = performance.now();

    function step(now) {
        const progress = Math.min((now - startTime) / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
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

// Generalized handler — works for ANY form with class "predict-form"
// and a data-endpoint attribute, so adding future disease modules
// (hypertension, respiratory illness) needs zero changes here.
document.querySelectorAll("form.predict-form").forEach((form) => {
    form.addEventListener("submit", async function (e) {
        e.preventDefault();

        const endpoint = form.dataset.endpoint;
        const resultPanel = form.closest("main").querySelector(".result-panel");

        const formData = new FormData(form);
        const data = {};
        formData.forEach((value, key) => {
            data[key] = parseFloat(value);
        });

        const resultEmpty = resultPanel.querySelector("#resultEmpty");
        const resultFilled = resultPanel.querySelector("#resultFilled");
        const statusLine = resultPanel.querySelector("#statusLine");

        resultEmpty.classList.add("is-hidden");
        resultFilled.classList.remove("is-hidden");
        statusLine.textContent = "Analyzing…";
        statusLine.className = "status-line";

        try {
            const response = await fetch(endpoint, {
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
            animateGauge(resultPanel, percentage, riskColors[result.risk_level] || "var(--accent)");

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
});