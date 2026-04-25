// role_state.js (kept at the old path because layout.html already includes it)

const ROLE_REFRESH_INTERVAL_MS = 5000;
const ROLE_ORDER = { customer: 0, operator: 1, admin: 2 };
let roleRefreshTimerId = null;
let lastKnownRole = null;

function hasRoleAtLeast(role, minimumRole) {
    return (ROLE_ORDER[role] ?? -1) >= ROLE_ORDER[minimumRole];
}

function setElementDisplay(element, isVisible, visibleDisplay = "block") {
    if (!element) {
        return;
    }

    element.style.display = isVisible ? visibleDisplay : "none";
}

function applyRoleVisibility(role) {
    const normalizedRole = role || "customer";
    const statusChanged = lastKnownRole !== normalizedRole;
    const isOperator = hasRoleAtLeast(normalizedRole, "operator");
    const isAdmin = normalizedRole === "admin";

    window.currentUserRole = normalizedRole;
    window.isOperator = isOperator;
    window.isAdmin = isAdmin;

    const userListItemEl = document.getElementById("user-list-item");
    const pendingApprovalItemEl = document.getElementById("pending-approval-item");
    const adminOrdersBtnEl = document.getElementById("adminOrdersBtn");
    const createChatBtn = document.getElementById("create-chat-btn");
    const addBtns = document.querySelectorAll(".btn-add-participants");
    const operatorOnly = document.querySelectorAll("[data-role-min='operator']");
    const adminOnly = document.querySelectorAll("[data-role-min='admin']");

    setElementDisplay(userListItemEl, isAdmin, "block");
    setElementDisplay(pendingApprovalItemEl, isOperator, "block");
    setElementDisplay(adminOrdersBtnEl, isOperator, "inline-block");
    setElementDisplay(createChatBtn, isOperator, "block");

    addBtns.forEach((btn) => setElementDisplay(btn, isOperator, "block"));
    operatorOnly.forEach((el) => setElementDisplay(el, isOperator, el.dataset.roleDisplay || "block"));
    adminOnly.forEach((el) => setElementDisplay(el, isAdmin, el.dataset.roleDisplay || "block"));

    if (statusChanged) {
        window.dispatchEvent(
            new CustomEvent("role-status-changed", {
                detail: { role: normalizedRole, isOperator, isAdmin },
            })
        );
    }

    lastKnownRole = normalizedRole;
}

async function fetchRoleStatus() {
    const token = await getTokenFromDatabase();
    if (!token) {
        return "customer";
    }

    const response = await fetch("/me", {
        method: "GET",
        headers: {
            "Authorization": `Bearer ${token}`,
            "Content-Type": "application/json",
        },
    });

    if (response.status === 401 || response.status === 403 || response.status === 404) {
        window.location.href = "/login";
        return "customer";
    }

    if (!response.ok) {
        throw new Error("Failed to fetch current user role");
    }

    const data = await response.json();
    applyRoleVisibility(data.role);
    return data.role;
}

async function refreshRoleState() {
    try {
        await fetchRoleStatus();
    } catch (error) {
        console.error("Error checking current user role:", error);
    }
}

function startRolePolling() {
    if (roleRefreshTimerId) {
        clearInterval(roleRefreshTimerId);
    }

    roleRefreshTimerId = setInterval(() => {
        if (document.visibilityState === "visible") {
            refreshRoleState();
        }
    }, ROLE_REFRESH_INTERVAL_MS);

    document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "visible") {
            refreshRoleState();
        }
    });

    window.addEventListener("focus", refreshRoleState);
    window.addEventListener("pageshow", refreshRoleState);
}

document.addEventListener("DOMContentLoaded", async function () {
    await refreshRoleState();
    startRolePolling();
});
