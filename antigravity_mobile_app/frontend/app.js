// =============================================================================
// app.js — Hamdam AI Booking Dashboard
// ARCHITECTURE NOTE: ALL event listeners are bound ONCE on stable parent
// elements using event delegation. No listener is ever attached inside a
// render function. This prevents the stacking-listener infinite-loop bug.
// =============================================================================

// ── Global State ──────────────────────────────────────────────────────────────
const SESSION_ID = "sess-" + Math.random().toString(36).substring(2, 11);
let activeBookings  = [];
let isFetchingBookings = false;   // guard: prevents concurrent fetch calls

const MOCK_HISTORY_DEFAULTS = [
    { booking_id: "BKG-MOCK1", provider_name: "Kamran Ahmed",  service: "Plumber",    avatar: "👨‍🔧", scheduled_slot: "10 May", status: "Completed", timestamp: "2026-05-10T10:00:00Z" },
    { booking_id: "BKG-MOCK2", provider_name: "M. Arsalan",    service: "Electrician", avatar: "⚡",   scheduled_slot: "15 Apr", status: "Completed", timestamp: "2026-05-15T12:00:00Z" },
    { booking_id: "BKG-MOCK3", provider_name: "Tariq Mahmood", service: "Carpenter",  avatar: "🪓",   scheduled_slot: "28 Mar", status: "Completed", timestamp: "2026-03-28T14:00:00Z" }
];
// Deep-clone so reset can restore to this
let historyBookings = MOCK_HISTORY_DEFAULTS.map(b => ({ ...b }));

// ── DOM References (queried once at startup) ──────────────────────────────────
const statusTimeDisplay       = document.getElementById("status-time-display");
const chatMessagesContainer   = document.getElementById("chat-messages-container");
const chatUserInput           = document.getElementById("chat-user-input");
const chatSendBtn             = document.getElementById("chat-send-btn");
const chatTypingIndicator     = document.getElementById("chat-typing-indicator");
const executionLogsContainer  = document.getElementById("execution-logs-container");
const activeBookingContainer  = document.getElementById("active-booking-container");
const activeBookingCard       = document.getElementById("active-booking-card");
const systemResetBtn          = document.getElementById("system-reset-btn");
const categorySelectorGrid    = document.getElementById("category-selector-grid");
const historyCardsContainer   = document.getElementById("history-cards-container");
const statsChipsRow           = document.querySelector(".stats-chips-row");

const stateNodes = {
    awaiting:  document.getElementById("state-node-awaiting"),
    searching: document.getElementById("state-node-searching"),
    slot:      document.getElementById("state-node-slot"),
    info:      document.getElementById("state-node-info"),
    booking:   document.getElementById("state-node-booking")
};
const stateLines = {
    line1: document.getElementById("state-line-1"),
    line2: document.getElementById("state-line-2"),
    line3: document.getElementById("state-line-3"),
    line4: document.getElementById("state-line-4")
};

// ── 1. Clock ──────────────────────────────────────────────────────────────────
function updateClock() {
    const now = new Date();
    let h = now.getHours(), m = now.getMinutes();
    const ampm = h >= 12 ? "PM" : "AM";
    h = h % 12 || 12;
    statusTimeDisplay.textContent = `${h}:${m < 10 ? "0" + m : m} ${ampm}`;
}
setInterval(updateClock, 1000);
updateClock();

// ── 2. Fetch Bookings (guarded — cannot run concurrently) ─────────────────────
async function fetchBookings() {
    if (isFetchingBookings) return;
    isFetchingBookings = true;
    try {
        const res = await fetch("/api/bookings");
        if (!res.ok) return;
        activeBookings = await res.json();

        // Sync any newly completed bookings into history
        const existingIds = new Set(historyBookings.map(h => h.booking_id));
        let changed = false;
        for (const b of activeBookings) {
            if (b.status === "Completed" && !existingIds.has(b.booking_id)) {
                historyBookings.unshift({
                    booking_id:    b.booking_id,
                    provider_name: b.provider_name,
                    service:       b.service,
                    avatar:        b.avatar || "💼",
                    scheduled_slot: b.scheduled_slot,
                    status:        "Completed",
                    timestamp:     b.timestamp
                });
                existingIds.add(b.booking_id);
                changed = true;
                logToConsole("SYSTEM", `Booking ${b.booking_id} completed — added to history.`);
            }
        }
        if (changed) renderHistoryBookings();
        renderActiveBookings();
        renderStatsChips();
    } catch {
        logToConsole("SYSTEM", "Failed to fetch active bookings from server.");
    } finally {
        isFetchingBookings = false;
    }
}

// ── 3. Render Active Booking Card ─────────────────────────────────────────────
function renderActiveBookings() {
    if (!activeBookings.length) {
        activeBookingContainer.style.display = "none";
        activeBookingCard.innerHTML = "";
        return;
    }
    const latest = activeBookings[activeBookings.length - 1];
    activeBookingContainer.style.display = "block";

    const statusClass = {
        Confirmed:  "status-confirmed",
        Dispatched: "status-dispatched",
        Completed:  "status-completed"
    }[latest.status] || "status-pending";

    const btnLabels = {
        Pending:    "Confirm Booking (Simulate)",
        Confirmed:  "Dispatch Worker (Simulate)",
        Dispatched: "Complete Service (Simulate)",
        Completed:  "Service Completed ✓"
    };
    const btnLabel = btnLabels[latest.status] || "Simulate";
    const isCompleted = latest.status === "Completed";

    activeBookingCard.innerHTML = `
        <div class="booking-card-header">
            <span class="booking-id-tag">${latest.booking_id}</span>
            <span class="booking-status ${statusClass}">${latest.status}</span>
        </div>
        <div class="booking-details-grid">
            <span class="booking-label">Service:</span>
            <span class="booking-val">${latest.avatar || "💼"} ${latest.service}</span>
            <span class="booking-label">Worker:</span>
            <span class="booking-val">${latest.provider_name}</span>
            <span class="booking-label">Time Slot:</span>
            <span class="booking-val">${latest.scheduled_slot}</span>
            <span class="booking-label">Rate:</span>
            <span class="booking-val">${latest.hourly_rate_pkr} PKR/hr</span>
        </div>
        ${isCompleted
            ? `<button class="booking-action-btn status-completed" style="cursor:default;" disabled>${btnLabel}</button>`
            : `<button class="booking-action-btn" id="simulate-progress-btn" data-id="${latest.booking_id}">${btnLabel}</button>`
        }
    `;
    // Listener is attached via delegation on activeBookingCard — see bottom of file
}

// ── 4. Simulate Booking State Progression ─────────────────────────────────────
async function simulateBookingState(bookingId) {
    logToConsole("SYSTEM", `Triggering status shift for ${bookingId}...`);
    try {
        const res = await fetch(`/api/bookings/${bookingId}/simulate`, { method: "POST" });
        if (res.ok) {
            const data = await res.json();
            logToConsole("SYSTEM", `Status updated: ${data.message}`);
            await fetchBookings();
        }
    } catch {
        logToConsole("SYSTEM", "Failed to update booking simulation status.");
    }
}

// ── 5. Render History Cards (no listeners attached here) ──────────────────────
function renderHistoryBookings() {
    if (!historyCardsContainer) return;
    historyCardsContainer.innerHTML = historyBookings.map(b => {
        const emoji = b.avatar ||
            (b.service === "Plumber" ? "👨‍🔧" :
             b.service === "Electrician" ? "⚡" :
             b.service === "Carpenter"  ? "🪓" :
             b.service === "Painter"    ? "🎨" : "📺");

        let dateDisplay = b.scheduled_slot || "";
        if (b.timestamp && b.timestamp.includes("T")) {
            try { dateDisplay = new Date(b.timestamp).toLocaleDateString("en-US", { day: "numeric", month: "short" }); }
            catch { /* keep original */ }
        }
        return `
            <div class="history-card">
                <div class="history-card-left">
                    <div class="history-card-header">
                        <span class="history-worker-avatar">${emoji}</span>
                        <div class="history-worker-info">
                            <span class="history-worker-name">${b.provider_name}</span>
                            <span class="history-service-date">${b.service} &bull; ${dateDisplay}</span>
                        </div>
                    </div>
                    <span class="history-badge status-completed">${b.status}</span>
                </div>
                <div class="history-card-right">
                    <button class="history-rebook-btn"
                            data-worker="${b.provider_name}"
                            data-service="${b.service}">Rebook</button>
                </div>
            </div>`;
    }).join("");
    // ← No addEventListener() here. Delegation handles clicks (see bottom).
}

// ── 6. Render Stats Chips (text only — no listeners attached inside) ──────────
// Chips use event delegation on statsChipsRow (bound once at bottom of file).
function renderStatsChips() {
    if (!statsChipsRow) return;
    const totalOrders   = historyBookings.length + activeBookings.filter(b => b.status !== "Completed").length;
    const uniqueWorkers = [...new Set(historyBookings.map(b => b.provider_name))];

    // Only update the text content of existing chips if they already exist,
    // otherwise build the markup once.
    let chipOrders   = document.getElementById("chip-total-orders");
    let chipWorkers  = document.getElementById("chip-saved-workers");

    if (!chipOrders || !chipWorkers) {
        // First render: create the chips (listeners added via delegation below)
        statsChipsRow.innerHTML = `
            <div class="stats-chip" id="chip-total-orders" style="cursor:pointer;">
                <span class="chip-icon">📦</span>
                <span class="chip-text" id="chip-orders-text">Total Orders: ${totalOrders}</span>
            </div>
            <div class="stats-chip" id="chip-saved-workers" style="cursor:pointer;">
                <span class="chip-icon">❤️</span>
                <span class="chip-text" id="chip-workers-text">Saved Workers: ${uniqueWorkers.length}</span>
            </div>`;
    } else {
        // Subsequent renders: just update text, no DOM rebuild = no listener rebuild
        document.getElementById("chip-orders-text").textContent  = `Total Orders: ${totalOrders}`;
        document.getElementById("chip-workers-text").textContent = `Saved Workers: ${uniqueWorkers.length}`;
    }
}

// ── 7. Append Chat Message ─────────────────────────────────────────────────────
function appendMessage(sender, text, isHtml = false) {
    const div = document.createElement("div");
    div.className = `message ${sender === "user" ? "outgoing" : "incoming"} animate-fade-in`;
    const now = new Date();
    let h = now.getHours(), m = now.getMinutes();
    const ampm = h >= 12 ? "PM" : "AM";
    h = h % 12 || 12;
    const timeStr = `${h}:${m < 10 ? "0" + m : m} ${ampm}`;
    div.innerHTML = `
        <div class="message-bubble">
            ${isHtml ? text : `<p>${escapeHTML(text)}</p>`}
            <span class="msg-time">${timeStr}</span>
        </div>`;
    chatMessagesContainer.appendChild(div);
    chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
}

// ── 8. Escape HTML ─────────────────────────────────────────────────────────────
function escapeHTML(t) {
    return t.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
             .replace(/"/g,"&quot;").replace(/'/g,"&#039;");
}

// ── 9. Console Log ─────────────────────────────────────────────────────────────
function logToConsole(tag, message) {
    const t = new Date().toTimeString().split(" ")[0];
    const d = document.createElement("div");
    d.className = "console-msg system-msg";
    d.innerHTML = `<span class="console-timestamp">[${t}]</span>
                   <span class="console-tag">[${tag}]</span>
                   <span class="console-text">${escapeHTML(message)}</span>`;
    executionLogsContainer.appendChild(d);
    executionLogsContainer.scrollTop = executionLogsContainer.scrollHeight;
}

// ── 10. Trace Card ─────────────────────────────────────────────────────────────
function appendTraceCard(step, type, message) {
    const card = document.createElement("div");
    card.className = `trace-card trace-${type.toLowerCase()}`;
    card.innerHTML = `
        <div class="trace-card-header">
            <span class="trace-label-badge">${type}</span>
            <span class="trace-step-tag">Step #${step}</span>
        </div>
        <div class="trace-message-body">${escapeHTML(message)}</div>`;
    executionLogsContainer.appendChild(card);
    executionLogsContainer.scrollTop = executionLogsContainer.scrollHeight;
    updateStateFlowDiagram(type, message);
}

// ── 11. State Flow Diagram ─────────────────────────────────────────────────────
function updateStateFlowDiagram(type, message) {
    const t = message.toLowerCase();
    Object.values(stateNodes).forEach(n => n && n.classList.remove("active", "completed"));
    Object.values(stateLines).forEach(l => l && l.classList.remove("active"));

    const activate = (nodes, lines) => {
        nodes.forEach(k => stateNodes[k] && stateNodes[k].classList.add(nodes.indexOf(k) < nodes.length - 1 ? "completed" : "active"));
        lines.forEach(k => stateLines[k] && stateLines[k].classList.add("active"));
    };

    if (t.includes("booking successfully") || t.includes("booking_id") || t.includes("confirm ho gayi")) {
        activate(["awaiting","searching","slot","info","booking"], ["line1","line2","line3","line4"]);
    } else if (t.includes("prerequisites met") || t.includes("phone number") || t.includes("naam aur phone")) {
        activate(["awaiting","searching","slot","info"], ["line1","line2","line3"]);
    } else if (t.includes("available time slots") || t.includes("select a slot") || t.includes("bypassing provider") || t.includes("selecting_slot")) {
        activate(["awaiting","searching","slot"], ["line1","line2"]);
    } else if (t.includes("find_providers") || t.includes("searching database") || t.includes("found matching")) {
        activate(["awaiting","searching"], ["line1"]);
    } else {
        stateNodes.awaiting && stateNodes.awaiting.classList.add("active");
    }
}

// ── 12. Format Server Response ─────────────────────────────────────────────────
function formatServerResponse(text) {
    let f = text.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
    f = f.replace(/`(.*?)`/g, '<code class="inline-code">$1</code>');
    f = f.replace(/\n/g, "<br>");
    return `<p>${f}</p>`;
}

// ── 13. Send Chat Message ──────────────────────────────────────────────────────
async function handleUserSend() {
    const text = chatUserInput.value.trim();
    if (!text) return;
    appendMessage("user", text);
    chatUserInput.value = "";
    chatTypingIndicator.style.display = "flex";
    chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
    logToConsole("USER", `Dispatched: "${text}"`);

    // AbortController: cancel the request if AI takes longer than 45 seconds
    const controller = new AbortController();
    const hardTimeout = setTimeout(() => controller.abort(), 45000);

    // "Still thinking" soft warning after 10 seconds so user knows it's not frozen
    const softWarning = setTimeout(() => {
        logToConsole("SYSTEM", "AI is still processing... (OpenAI API ka response aa raha hai, please wait)");
    }, 10000);

    try {
        const res = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: SESSION_ID, message: text }),
            signal: controller.signal
        });
        clearTimeout(hardTimeout);
        clearTimeout(softWarning);

        if (res.ok) {
            const data = await res.json();
            if (data.trace && data.trace.length) {
                let delay = 0;
                data.trace.forEach((s, i) => {
                    setTimeout(() => {
                        appendTraceCard(s.step, s.type, s.message);
                        if (i === data.trace.length - 1) {
                            setTimeout(() => {
                                chatTypingIndicator.style.display = "none";
                                appendMessage("assistant", formatServerResponse(data.response), true);
                                fetchBookings();  // safe — guard prevents stacking
                            }, 500);
                        }
                    }, delay);
                    delay += 650;
                });
            } else {
                chatTypingIndicator.style.display = "none";
                appendMessage("assistant", formatServerResponse(data.response), true);
                fetchBookings();
            }
        } else {
            chatTypingIndicator.style.display = "none";
            appendMessage("assistant", "Sorry, server side communication errored out.");
        }
    } catch (e) {
        clearTimeout(hardTimeout);
        clearTimeout(softWarning);
        chatTypingIndicator.style.display = "none";
        if (e.name === "AbortError") {
            // Timeout — show friendly message and let user retry
            appendMessage("assistant", formatServerResponse(
                "⏱️ **Response mein zyada waqt lag raha hai.** OpenAI API slow hai abhi.\n\nKripya dobara message bhejein ya kuch seconds baad try karein."
            ), true);
            logToConsole("ERROR", "Request timed out after 45 seconds (AbortError).");
        } else {
            appendMessage("assistant", "Unable to connect to the orchestrator. Is the backend server running?");
            logToConsole("ERROR", `Fetch failed: ${e.message}`);
        }
    }
}

// =============================================================================
// EVENT LISTENERS — all bound ONCE on stable DOM nodes (never inside renders)
// =============================================================================

// Send button & Enter key
chatSendBtn.addEventListener("click", handleUserSend);
chatUserInput.addEventListener("keydown", e => { if (e.key === "Enter") handleUserSend(); });

// Rebook buttons — delegation on stable history container
historyCardsContainer.addEventListener("click", e => {
    const btn = e.target.closest(".history-rebook-btn");
    if (!btn) return;
    e.stopPropagation();
    const payloadMsg = `Rebook ${btn.dataset.worker} for ${btn.dataset.service}`;
    logToConsole("USER", `One-tap rebook: "${payloadMsg}"`);
    chatUserInput.value = payloadMsg;
    handleUserSend();
});

// Simulate progress button — delegation on active booking card container
activeBookingCard.addEventListener("click", e => {
    const btn = e.target.closest("#simulate-progress-btn");
    if (!btn) return;
    simulateBookingState(btn.dataset.id);
});

// Stats chips — delegation on stable chips row container
statsChipsRow.addEventListener("click", e => {
    const chip = e.target.closest(".stats-chip");
    if (!chip) return;
    const id = chip.id;
    if (id === "chip-total-orders") {
        const total = historyBookings.length + activeBookings.filter(b => b.status !== "Completed").length;
        logToConsole("SYSTEM", `Total orders: ${total}`);
        appendMessage("assistant", formatServerResponse(`Aap ne Hamdam ke zariye ab tak total **${total}** orders place kiye hain. Shukriya! 😊`), true);
    } else if (id === "chip-saved-workers") {
        const workers = [...new Set(historyBookings.map(b => b.provider_name))].join(", ");
        logToConsole("SYSTEM", `Saved workers: ${workers}`);
        appendMessage("assistant", formatServerResponse(`Aap ke saved workers: **${workers}**. Rebook karne ke liye history card mein "Rebook" button dabayein!`), true);
    }
});

// Category quick-select grid — delegation
categorySelectorGrid.addEventListener("click", e => {
    const card = e.target.closest(".category-card");
    if (!card) return;
    const queries = {
        "Plumber":         "Mujhe plumber chahye urgent",
        "Electrician":     "Urgent electrician bulwa do",
        "Carpenter":       "Carpenter ki zaroorat hai furniture repair ke liye",
        "Painter":         "Ghar paint karwana hai painter milega?",
        "Appliance Repair": "Mera AC kharab ho gya hai repair karwana hai"
    };
    const q = queries[card.dataset.service];
    if (q) { chatUserInput.value = q; handleUserSend(); }
});

// Reset button
systemResetBtn.addEventListener("click", async () => {
    logToConsole("SYSTEM", "Resetting agent database variables...");
    try {
        const res = await fetch("/api/reset", { method: "POST" });
        if (res.ok) {
            logToConsole("SYSTEM", "Database successfully wiped and restored.");
            historyBookings = MOCK_HISTORY_DEFAULTS.map(b => ({ ...b }));
            activeBookings  = [];
            renderHistoryBookings();
            renderActiveBookings();
            renderStatsChips();
            chatMessagesContainer.innerHTML = `
                <div class="message incoming animate-fade-in">
                    <div class="message-bubble">
                        <p>System reset! Sessions cleared. Main kis tarah madad kar sakta hoon?</p>
                        <span class="msg-time">Just Now</span>
                    </div>
                </div>`;
            Object.values(stateNodes).forEach(n => n && n.classList.remove("active","completed"));
            Object.values(stateLines).forEach(l => l && l.classList.remove("active"));
            if (stateNodes.awaiting) stateNodes.awaiting.classList.add("active");
        }
    } catch {
        logToConsole("SYSTEM", "Error during system reset.");
    }
});

// =============================================================================
// INITIAL RENDER
// =============================================================================
renderHistoryBookings();
renderStatsChips();
fetchBookings();   // async — populates active bookings and re-renders chips/history
