// auth.js
let cachedAccessToken = null;
let cachedUserId = null;
let refreshTokenPromise = null;
const TOKEN_EXPIRY_SKEW_MS = 30 * 1000;

localStorage.removeItem("access_token");
localStorage.removeItem("user_id");

function decodeJwtPayload(token) {
    if (!token || typeof token !== "string") {
        return null;
    }

    const parts = token.split(".");
    if (parts.length !== 3) {
        return null;
    }

    try {
        const base64Url = parts[1];
        const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
        const padding = "=".repeat((4 - (base64.length % 4)) % 4);
        const json = atob(base64 + padding);
        return JSON.parse(json);
    } catch (error) {
        console.error("Failed to decode JWT payload:", error);
        return null;
    }
}

function isTokenExpired(token) {
    const payload = decodeJwtPayload(token);
    if (!payload || typeof payload.exp !== "number") {
        return true;
    }

    return Date.now() >= (payload.exp * 1000) - TOKEN_EXPIRY_SKEW_MS;
}

function syncCachedUserIdFromToken(token) {
    const payload = decodeJwtPayload(token);
    if (payload && payload.sub) {
        cachedUserId = payload.sub;
    }
}

async function getTokenFromDatabase() {
    if (cachedAccessToken && !isTokenExpired(cachedAccessToken)) {
        syncCachedUserIdFromToken(cachedAccessToken);
        return cachedAccessToken;
    }

    if (cachedAccessToken) {
        cachedAccessToken = null;
        cachedUserId = null;
    }

    const newToken = await getNewAccessToken();
    if (!newToken) {
        cachedUserId = null;
        console.log("Не удалось получить токен. Перенаправляем на страницу логина.");
        window.location.href = '/login';
        return null;
    }

    return newToken;
}

function getCurrentUserId() {
    return cachedUserId;
}

function setCurrentUserId(userId) {
    cachedUserId = userId;
}


// Функция для получения нового access token с использованием refresh token
async function getNewAccessToken() {
    if (!refreshTokenPromise) {
        refreshTokenPromise = (async () => {
            const response = await fetch('/refresh-token', {
                method: 'POST',
                credentials: 'include',
            });

            if (!response.ok) {
                console.log("Отсутствует refresh token. Перенаправляем на страницу логина.");
                return null;
            }

            const data = await response.json();
            if (data.access_token) {
                cachedAccessToken = data.access_token;
                cachedUserId = data.user_id || cachedUserId;
                return data.access_token;
            }

            console.log("Не удалось обновить токен. Перенаправляем на страницу логина.");
            return null;
        })().finally(() => {
            refreshTokenPromise = null;
        });
    }

    return refreshTokenPromise;
}

async function logoutUser(event) {
    if (event) {
        event.preventDefault();
    }

    try {
        await fetch('/logout', {
            method: 'POST',
            credentials: 'include',
        });
    } catch (error) {
        console.error('Logout error:', error);
    } finally {
        cachedAccessToken = null;
        cachedUserId = null;
        refreshTokenPromise = null;
        localStorage.removeItem('access_token');
        localStorage.removeItem('user_id');
        window.location.href = '/login';
    }
}

document.addEventListener('DOMContentLoaded', function () {
    const logoutLink = document.getElementById('logout-link');
    if (logoutLink) {
        logoutLink.addEventListener('click', logoutUser);
    }
});
