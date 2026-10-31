const CIRCUMFERENCE = 364.42;

function resetGauge(panel) {
    // Clear any previous result so an old gauge is never shown beside a new message
    const arc = panel.querySelector("#gaugeArc");
    arc.style.transition = "none";
    arc.style.strokeDashoffset = CIRCUMFERENCE;
    panel.querySelector("#gaugeValue").textContent = "—";
    panel.querySelector("#gaugeLabel").textContent = "";
    const note = panel.querySelector(".saved-note");
    if (note) note.remove();
}

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

function showSavedNote(statusLine, result) {
    const note = document.createElement("p");
    note.className = "saved-note";
    note.append(`Saved for patient ${result.patient_code} as assessment #${result.assessment_id}. `);
    const link = document.createElement("a");
    link.href = `/assessment/${result.assessment_id}`;
    link.textContent = "View record";
    note.append(link);
    statusLine.insertAdjacentElement("afterend", note);
}

// Works for ANY form with class "predict-form" and a data-endpoint attribute,
// so every disease module shares this one script.
document.querySelectorAll("form.predict-form").forEach((form) => {
    form.addEventListener("submit", async function (e) {
        e.preventDefault();

        const endpoint = form.dataset.endpoint;
        const resultPanel = form.closest("main").querySelector(".result-panel");

        const formData = new FormData(form);
        const data = {};
        formData.forEach((value, key) => {
            // The patient code is text; every other field is a number
            data[key] = key === "patient_code" ? value.trim() : parseFloat(value);
        });

        const resultEmpty = resultPanel.querySelector("#resultEmpty");
        const resultFilled = resultPanel.querySelector("#resultFilled");
        const statusLine = resultPanel.querySelector("#statusLine");

        resultEmpty.classList.add("is-hidden");
        resultFilled.classList.remove("is-hidden");
        resetGauge(resultPanel);
        statusLine.textContent = "Analyzing…";
        statusLine.className = "status-line";

        try {
            const response = await fetch(endpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(data)
            });

            if (response.status === 401) {   // the session ended: go back to sign in, then return here
                window.location.href = "/login?next=" + encodeURIComponent(window.location.pathname);
                return;
            }

            const result = await response.json();

            if (result.error) {
                statusLine.textContent = result.error;
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
            showSavedNote(statusLine, result);

        } catch (err) {
            statusLine.textContent = "Something went wrong. Please try again.";
            statusLine.className = "status-line status-positive";
        }
    });
});
