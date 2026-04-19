// user_list.js
let currentPage = 1;
let currentSortBy = "name";
let currentSortOrder = "asc";
let currentSearch = "";
let currentRoleFilter = "all";
let currentPageSize = 10;
let searchTimeout = null;
let authToken = null;

document.addEventListener("DOMContentLoaded", async function () {
    const token = await getTokenFromDatabase();

    if (!token) {
        window.location.href = '/login';
        return;
    }

    authToken = token;
    bindSortHandlers();
    bindSearchHandler();
    bindFilterHandler();
    bindPageSizeHandler();
    loadUsers(1).catch(error => {
        console.error("Error loading users:", error);
        alert(error.message);
    });
});

function buildUsersUrl(page) {
    const params = new URLSearchParams({
        page: String(page),
        page_size: String(currentPageSize),
        sort_by: currentSortBy,
        order: currentSortOrder,
    });

    const searchValue = currentSearch.trim();
    if (searchValue) {
        params.set("search", searchValue);
    }

    if (currentRoleFilter !== "all") {
        params.set("role", currentRoleFilter);
    }

    return `/users/?${params.toString()}`;
}

async function loadUsers(page = 1) {
    currentPage = page;

    const response = await fetch(buildUsersUrl(page), {
        method: 'GET',
        headers: {
            'Authorization': `Bearer ${authToken}`,
            'Content-Type': 'application/json'
        }
    });

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to load users (${response.status})`);
    }

    const data = await response.json();
    const users = Array.isArray(data) ? data : data.users;
    if (!Array.isArray(users)) {
        console.error("User list is not in expected format");
        return;
    }

    currentPage = data.page || page;
    const totalPages = data.total_pages || data.totalPages || (data.total ? Math.ceil(data.total / currentPageSize) : 0);
    renderUserTable(users);
    renderPagination(totalPages, currentPage);
    updateSortIndicators();
}

function renderUserTable(users) {
    const userTableBody = document.getElementById('userTableBody');
    if (!userTableBody) {
        return;
    }

    userTableBody.innerHTML = '';

    if (!users.length) {
        const emptyRow = document.createElement('tr');
        emptyRow.innerHTML = `
            <td colspan="5" class="text-center text-muted">Пользователи не найдены</td>
        `;
        userTableBody.appendChild(emptyRow);
        return;
    }

    users.forEach(user => {
        const row = document.createElement('tr');
        row.innerHTML = `
        <td>${user.id}</td>
        <td>${user.name}</td>
        <td>${user.email}</td>
        <td>${user.role === 'superadmin' ? 'супер-админ' : 'пользователь'}</td>
        <td>${user.role !== 'superadmin' ? `<button class="btn btn-sm btn-success promote-btn" data-id="${user.id}">Повысить до супер-админа</button>` : ''}</td>
    `;
        userTableBody.appendChild(row);
    });

    document.querySelectorAll(".promote-btn").forEach(button => {
        button.addEventListener("click", function () {
            const userId = this.getAttribute("data-id");
            promoteUserToSuperadmin(userId);
        });
    });
}

function renderPagination(totalPages, activePage) {
    const paginationContainer = document.getElementById('paginationContainer');
    if (!paginationContainer) {
        return;
    }

    paginationContainer.innerHTML = '';

    if (totalPages <= 1) {
        return;
    }

    for (let page = 1; page <= totalPages; page++) {
        const pageItem = document.createElement('li');
        pageItem.className = `page-item${page === activePage ? ' active' : ''}`;
        pageItem.innerHTML = `<a class="page-link" href="#">${page}</a>`;

        pageItem.addEventListener('click', (e) => {
            e.preventDefault();
            loadUsers(page).catch(error => {
                console.error("Error loading users page:", error);
                alert(error.message);
            });
        });

        paginationContainer.appendChild(pageItem);
    }
}

function bindSearchHandler() {
    const searchInput = document.getElementById('search');
    if (!searchInput) {
        return;
    }

    searchInput.addEventListener('input', function () {
        currentSearch = this.value;

        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            loadUsers(1).catch(error => {
                console.error("Error loading filtered users:", error);
                alert(error.message);
            });
        }, 300);
    });
}

function bindFilterHandler() {
    const roleFilter = document.getElementById('roleFilter');
    const resetFilters = document.getElementById('resetFilters');
    const pageSizeSelect = document.getElementById('pageSizeSelect');

    if (roleFilter) {
        roleFilter.addEventListener('change', function () {
            currentRoleFilter = this.value;
            loadUsers(1).catch(error => {
                console.error("Error loading filtered users:", error);
                alert(error.message);
            });
        });
    }

    if (resetFilters) {
        resetFilters.addEventListener('click', function () {
            currentSearch = "";
            currentRoleFilter = "all";
            currentPageSize = 10;
            searchTimeout = null;

            const searchInput = document.getElementById('search');
            if (searchInput) {
                searchInput.value = "";
            }
            if (roleFilter) {
                roleFilter.value = "all";
            }
            if (pageSizeSelect) {
                pageSizeSelect.value = "10";
            }

            loadUsers(1).catch(error => {
                console.error("Error resetting user filters:", error);
                alert(error.message);
            });
        });
    }
}

function bindPageSizeHandler() {
    const pageSizeSelect = document.getElementById('pageSizeSelect');
    if (!pageSizeSelect) {
        return;
    }

    pageSizeSelect.addEventListener('change', function () {
        currentPageSize = parseInt(this.value, 10) || 10;
        loadUsers(1).catch(error => {
            console.error("Error loading users after page size change:", error);
            alert(error.message);
        });
    });
}

function bindSortHandlers() {
    document.querySelectorAll('[data-sort]').forEach(header => {
        header.addEventListener('click', () => {
            const sortBy = header.getAttribute('data-sort');
            if (currentSortBy === sortBy) {
                currentSortOrder = currentSortOrder === 'asc' ? 'desc' : 'asc';
            } else {
                currentSortBy = sortBy;
                currentSortOrder = sortBy === 'role' ? 'desc' : 'asc';
            }

            loadUsers(1).catch(error => {
                console.error("Error loading sorted users:", error);
                alert(error.message);
            });
        });
    });
}

function updateSortIndicators() {
    document.querySelectorAll('[data-sort]').forEach(header => {
        const indicator = header.querySelector('.sort-indicator');
        if (!indicator) {
            return;
        }

        const sortBy = header.getAttribute('data-sort');
        if (sortBy === currentSortBy) {
            indicator.textContent = currentSortOrder === 'asc' ? ' ▲' : ' ▼';
        } else {
            indicator.textContent = '';
        }
    });
}

async function promoteUserToSuperadmin(userId) {
    const token = authToken || await getTokenFromDatabase();
    fetch(`/users/promote/${userId}`, {
        method: 'PUT',
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        }
    })
        .then(response => {
            if (response.ok) {
                alert("User successfully promoted to super admin.");
                authToken = token;
                loadUsers(currentPage).catch(error => {
                    console.error("Error reloading users after promotion:", error);
                });
            } else {
                return response.json().then(data => {
                    throw new Error(data.detail);
                });
            }
        })
        .catch(error => {
            console.error("Error promoting user:", error);
            alert("Error promoting user: " + error.message);
        });
}
