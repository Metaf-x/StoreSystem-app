// login.js
document.addEventListener('DOMContentLoaded', async function () {
    localStorage.removeItem('access_token');

    try {
        const response = await fetch('/refresh-token', {
            method: 'POST',
            credentials: 'include',
        });

        if (response.ok) {
            const data = await response.json();
            if (data.access_token) {
                localStorage.removeItem('access_token');
                window.location.href = '/products';
                return;
            }
        }
    } catch (error) {
        console.error('Error refreshing token:', error);
    }

    document.getElementById('loginForm').addEventListener('submit', async function (e) {
        e.preventDefault();

        const email = document.getElementById('email').value;
        const password = document.getElementById('password').value;
        const rememberMe = document.getElementById('rememberMe').checked;

        try {
            const response = await fetch('/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'include',
                body: JSON.stringify({ email, password, remember_me: rememberMe })
            });

            const data = await response.json();
            if (response.ok && data.access_token) {
                localStorage.removeItem('access_token');
                window.location.href = '/products';
            } else {
                alert("Login failed: " + (data.detail || "Unknown error"));
            }
        } catch (error) {
            console.error('Login error:', error);
        }
    });
});
