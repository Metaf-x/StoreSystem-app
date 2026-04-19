document.addEventListener('DOMContentLoaded', function () {
    document.getElementById('registerForm').addEventListener('submit', function (e) {
        e.preventDefault();

        let username = document.getElementById('username').value;
        let email = document.getElementById('email').value;
        let password = document.getElementById('password').value;
        let valid = true;

        // Функция для сброса ошибок
        function resetError(elementId) {
            const errorElement = document.getElementById(elementId);
            errorElement.style.display = 'none';
            errorElement.innerText = '';  // очищаем текст ошибки
        }

        // Функция для отображения ошибки
        function showError(elementId, message) {
            const errorElement = document.getElementById(elementId);
            errorElement.innerText = message;
            errorElement.style.display = 'block';
        }

        // Сброс сообщений об ошибках
        resetError('usernameError');
        resetError('emailError');
        resetError('passwordError');
        document.getElementById('successMessage').style.display = 'none';

        // Валидация имени пользователя
        const sqlScriptPattern = /(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|SCRIPT|<script|alert|onload|onerror)\b)/i;
        if (username.trim() === "" || /^\s/.test(username)) {
            showError('usernameError', "Имя не может содержать только пробелы или начинаться с пробела.");
            valid = false;
        } else if (username.length < 3 || username.length > 50) {
            showError('usernameError', "Имя пользователя должно быть от 3 до 50 символов.");
            valid = false;
        } else if (sqlScriptPattern.test(username)) {
            showError('usernameError', "Имя не может содержать запрещенные символы или SQL/скриптовые команды.");
            valid = false;
        }

        // Валидация email
        const emailPattern = /^[a-zA-Z0-9](?!.*\.\.)[a-zA-Z0-9!#$%&'*+/=?^_`{|}~.-]{0,62}[a-zA-Z0-9]@(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$/;
        if (!emailPattern.test(email)) {
            showError('emailError', "В поле email присутствуют недопустимые символы.");
            valid = false;
        }
        // Валидация пароля
        if (password.trim() === "" || /^\s/.test(password)) {
            showError('passwordError', "Пароль не может содержать только пробелы или начинаться с пробела.");
            valid = false;
        } else if (password.length < 8) {
            showError('passwordError', "Пароль должен быть более 8 символов.");
            valid = false;
        }

        if (password.length < 8) {
            document.getElementById('passwordError').innerText = "Пароль должен быть более 8 символов.";
            document.getElementById('passwordError').style.display = 'block';
            valid = false;
        }

        // Если валидация успешна
        if (valid) {
            // Отправка данных на сервер через fetch
                fetch('/register', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    name: username,
                    email: email,
                    password: password
                })
            })
                .then(response => {
                    if (response.status === 201) {
                        // Показать сообщение об успешной регистрации
                        const successMessage = document.getElementById('successMessage');
                        successMessage.style.display = 'block';

                        // Ждем 3 секунды перед перенаправлением
                        setTimeout(() => {
                            window.location.href = "/login";
                        }, 3000);
                    } else {
                        return response.json().then(data => {
                            // Если возникла ошибка, отображаем сообщение об ошибке
                            if (data.detail === "Email already registered") {
                                document.getElementById('emailError').innerText = "Этот email уже зарегистрирован.";
                                document.getElementById('emailError').style.display = 'block';
                            } else if (data.detail === "Invalid email format.") {
                                document.getElementById('emailError').innerText = "В поле email присутствуют недопустимые символы.";
                                document.getElementById('emailError').style.display = 'block';
                            } else if (data.detail === "Name contains invalid characters.") {
                                document.getElementById('usernameError').innerText = "Имя не может содержать только пробелы или начинаться с пробела.";
                                document.getElementById('usernameError').style.display = 'block';
                            } else if (data.detail === "Password contains invalid characters.") {
                                document.getElementById('passwordError').innerText = "Пароль не может содержать только пробелы или начинаться с пробела.";
                                document.getElementById('passwordError').style.display = 'block';
                            } else {
                                alert("Ошибка при регистрации");
                            }
                        });
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert("Ошибка при отправке данных");
                });
        }
    });
});
