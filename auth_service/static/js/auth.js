// auth.js
let cachedAccessToken = null;
let cachedUserId = null;
let refreshTokenPromise = null;

localStorage.removeItem("access_token");
localStorage.removeItem("user_id");

async function getTokenFromDatabase() {
    if (cachedAccessToken) {
        const tokenInfo = await verifyTokenOnServer(cachedAccessToken);
        if (tokenInfo && tokenInfo.valid) {
            cachedUserId = tokenInfo.user_id || cachedUserId;
            return cachedAccessToken;
        }

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

// Проверка токена на сервере перед выполнением других действий
async function verifyTokenOnServer(token) {
    const response = await fetch(`/verify-token`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token })
    });

    return await response.json();
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
