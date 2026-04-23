// check_superadmin.js

const SUPERADMIN_REFRESH_INTERVAL_MS = 5000;
let superadminRefreshTimerId = null;
let lastKnownSuperadminStatus = null;

function setElementDisplay(element, isVisible, visibleDisplay = "block") {
    if (!element) {
        return;
    }

    element.style.display = isVisible ? visibleDisplay : "none";
}

function applySuperAdminVisibility(isSuperAdmin) {
    const normalizedStatus = Boolean(isSuperAdmin);
    const statusChanged = lastKnownSuperadminStatus !== normalizedStatus;

    window.isSuperAdmin = normalizedStatus;

    const userListItemEl = document.getElementById("user-list-item");
    const pendingApprovalItemEl = document.getElementById("pending-approval-item");
    const adminOrdersBtnEl = document.getElementById("adminOrdersBtn");
    const createChatBtn = document.getElementById("create-chat-btn");
    const addBtns = document.querySelectorAll(".btn-add-participants");

    setElementDisplay(userListItemEl, normalizedStatus, "block");
    setElementDisplay(pendingApprovalItemEl, normalizedStatus, "block");
    setElementDisplay(adminOrdersBtnEl, normalizedStatus, "inline-block");
    setElementDisplay(createChatBtn, normalizedStatus, "block");

    addBtns.forEach((btn) => {
        setElementDisplay(btn, normalizedStatus, "block");
    });

    if (statusChanged) {
        window.dispatchEvent(
            new CustomEvent("superadmin-status-changed", {
                detail: { isSuperAdmin: normalizedStatus },
            })
        );
    }

    lastKnownSuperadminStatus = normalizedStatus;
}

async function fetchSuperAdminStatus() {
    const token = await getTokenFromDatabase();
    if (!token) {
        return false;
    }

    const response = await fetch("/check-superadmin", {
        method: "GET",
        headers: {
            "Authorization": `Bearer ${token}`,
            "Content-Type": "application/json",
        },
    });

    if (response.status === 401 || response.status === 403 || response.status === 404) {
        window.location.href = "/login";
        return false;
    }

    if (!response.ok) {
        throw new Error("Failed to fetch admin status");
    }

    const data = await response.json();
    applySuperAdminVisibility(data.is_superadmin);
    return Boolean(data.is_superadmin);
}

async function refreshSuperAdminState() {
    try {
        await fetchSuperAdminStatus();
    } catch (error) {
        console.error("Error checking super admin status:", error);
    }
}

function startSuperAdminPolling() {
    if (superadminRefreshTimerId) {
        clearInterval(superadminRefreshTimerId);
    }

    superadminRefreshTimerId = setInterval(() => {
        if (document.visibilityState === "visible") {
            refreshSuperAdminState();
        }
    }, SUPERADMIN_REFRESH_INTERVAL_MS);

    document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "visible") {
            refreshSuperAdminState();
        }
    });

    window.addEventListener("focus", refreshSuperAdminState);
    window.addEventListener("pageshow", refreshSuperAdminState);
}

document.addEventListener("DOMContentLoaded", async function () {
    await refreshSuperAdminState();
    startSuperAdminPolling();
});
