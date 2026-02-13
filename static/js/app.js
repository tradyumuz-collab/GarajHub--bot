// ==================== GLOBAL O'ZGARUVCHILAR ====================
let currentUser = null;
let currentPage = 'login';
let userGrowthChart = null;
let distributionChart = null;
let activityChart = null;
let startupDetailChart = null;
let lastCheckTime = null;
let notificationsInterval = null;

// ==================== DOM YUKLANGANDA ====================
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

// ==================== ASOSIY FUNKSIYALAR ====================
function initializeApp() {
    // Event listenerlarni sozlash
    setupEventListeners();
    
    // Auth tekshirish
    checkAuth();
    
    // Loading ekranini yashirish
    setTimeout(() => {
        document.getElementById('loadingScreen').style.opacity = '0';
        setTimeout(() => {
            document.getElementById('loadingScreen').style.display = 'none';
        }, 300);
    }, 500);
    
    // Notification auto-check
    startNotificationChecker();
    
    // Offline/Online detection
    setupConnectionWatcher();
}

function setupConnectionWatcher() {
    window.addEventListener('online', () => {
        showToast('Internet ulandi', 'success');
        if (currentUser) {
            loadDashboard();
        }
    });
    
    window.addEventListener('offline', () => {
        showToast('Internet uzildi', 'error');
    });
    
    // Dastlabki tekshirish
    if (!navigator.onLine) {
        showToast('Internet ulanmagan', 'warning');
    }
}

// ==================== EVENT LISTENERLAR ====================
function setupEventListeners() {
    // Login form
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }
    
    // Logout
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', handleLogout);
    }
    
    // Menu items
    document.querySelectorAll('.menu li').forEach(item => {
        item.addEventListener('click', function() {
            const page = this.dataset.page;
            if (page && currentUser) {
                showPage(page);
                setActiveMenuItem(page);
                updateBreadcrumb(page);
            }
        });
    });
    
    // Menu toggle (mobil uchun)
    const menuToggle = document.getElementById('menuToggle');
    if (menuToggle) {
        menuToggle.addEventListener('click', function() {
            const sidebar = document.querySelector('.sidebar');
            if (sidebar) {
                sidebar.classList.toggle('active');
            }
        });
    }
    
    // Theme toggle
    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
        themeToggle.addEventListener('change', toggleTheme);
        
        // Saqlangan temani yuklash
        const savedTheme = localStorage.getItem('theme') || 'light';
        document.documentElement.setAttribute('data-theme', savedTheme);
        themeToggle.checked = savedTheme === 'dark';
    }
    
    // Password ko'rish
    const togglePassword = document.getElementById('togglePassword');
    if (togglePassword) {
        togglePassword.addEventListener('click', function() {
            const passwordInput = document.getElementById('loginPassword');
            if (!passwordInput) return;
            
            const icon = this.querySelector('i');
            if (passwordInput.type === 'password') {
                passwordInput.type = 'text';
                if (icon) {
                    icon.classList.remove('fa-eye');
                    icon.classList.add('fa-eye-slash');
                }
            } else {
                passwordInput.type = 'password';
                if (icon) {
                    icon.classList.remove('fa-eye-slash');
                    icon.classList.add('fa-eye');
                }
            }
        });
    }
    
    // Broadcast form
    const broadcastForm = document.getElementById('broadcastForm');
    if (broadcastForm) {
        broadcastForm.addEventListener('submit', handleBroadcast);
    }
    
    // Broadcast modal form
    const broadcastFormModal = document.getElementById('broadcastFormModal');
    if (broadcastFormModal) {
        broadcastFormModal.addEventListener('submit', handleBroadcastModal);
    }
    
    // Settings form
    const generalSettingsForm = document.getElementById('generalSettingsForm');
    if (generalSettingsForm) {
        generalSettingsForm.addEventListener('submit', handleSettingsSave);
    }
    
    // Add admin form
    const addAdminForm = document.getElementById('addAdminForm');
    if (addAdminForm) {
        addAdminForm.addEventListener('submit', handleAddAdmin);
    }
    
    // Search
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('input', handleSearch);
    }
    
    const userSearch = document.getElementById('userSearch');
    if (userSearch) {
        userSearch.addEventListener('input', debounce(() => loadUsers(1), 500));
    }
    
    const startupSearch = document.getElementById('startupSearch');
    if (startupSearch) {
        startupSearch.addEventListener('input', debounce(() => loadStartups(1), 500));
    }
    
    // Settings tabs
    document.querySelectorAll('.settings-tab').forEach(tab => {
        tab.addEventListener('click', function() {
            const tabId = this.dataset.tab;
            
            // Tablarni faollashtirish
            document.querySelectorAll('.settings-tab').forEach(t => t.classList.remove('active'));
            this.classList.add('active');
            
            // Kontentni ko'rsatish
            document.querySelectorAll('.settings-tab-content').forEach(content => {
                content.classList.remove('active');
            });
            const tabContent = document.getElementById(tabId + 'Tab');
            if (tabContent) {
                tabContent.classList.add('active');
            }
        });
    });
    
    // Modal overlay click
    const modalOverlay = document.getElementById('modalOverlay');
    if (modalOverlay) {
        modalOverlay.addEventListener('click', function(e) {
            if (e.target === this) {
                closeModal();
            }
        });
    }
    
    // Notification button
    const notificationBtn = document.getElementById('notificationBtn');
    if (notificationBtn) {
        notificationBtn.addEventListener('click', showNotifications);
    }
    
    // Keyboard shortcuts
    document.addEventListener('keydown', handleKeyboardShortcuts);
    
    // Dashboard filter buttons
    const growthFilter = document.getElementById('growthFilter');
    if (growthFilter) {
        growthFilter.addEventListener('change', () => loadUserGrowthChart());
    }
    
    // Activity filter buttons
    document.querySelectorAll('.activity-filter-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            filterActivity(this.dataset.type);
        });
    });
    
    // User filter
    const userFilter = document.getElementById('userFilter');
    if (userFilter) {
        userFilter.addEventListener('change', () => loadUsers(1));
    }
    
    // Startup filter
    const startupFilter = document.getElementById('startupFilter');
    if (startupFilter) {
        startupFilter.addEventListener('change', () => loadStartups(1));
    }
    
    // Stats period filter
    const statsPeriod = document.getElementById('statsPeriod');
    if (statsPeriod) {
        statsPeriod.addEventListener('change', loadDetailedStatistics);
    }
    
    // Notification settings save
    const notificationSettingsBtn = document.getElementById('notificationSettingsBtn');
    if (notificationSettingsBtn) {
        notificationSettingsBtn.addEventListener('click', saveNotificationSettings);
    }
    
    // Export buttons
    const exportUsersBtn = document.getElementById('exportUsersBtn');
    if (exportUsersBtn) {
        exportUsersBtn.addEventListener('click', exportUsers);
    }
    
    const exportStartupsBtn = document.getElementById('exportStartupsBtn');
    if (exportStartupsBtn) {
        exportStartupsBtn.addEventListener('click', exportStartups);
    }
}

// ==================== AUTH FUNKSIYALARI ====================
async function checkAuth() {
    try {
        showLoading();
        const response = await fetch('/api/check_auth');
        const data = await response.json();
        
        hideLoading();
        
        if (data.authenticated) {
            currentUser = data.user;
            showPage('dashboard');
            updateUserInfo();
            loadDashboard();
            startNotificationChecker();
        } else {
            showPage('login');
        }
    } catch (error) {
        console.error('Auth tekshirish xatosi:', error);
        hideLoading();
        showPage('login');
        if (navigator.onLine) {
            showToast('Serverga ulanib bo\'lmadi', 'error');
        }
    }
}

async function handleLogin(e) {
    e.preventDefault();
    
    const username = document.getElementById('loginUsername')?.value;
    const password = document.getElementById('loginPassword')?.value;
    
    if (!username || !password) {
        showToast('Login va parolni kiriting', 'error');
        return;
    }
    
    try {
        showLoading();
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, password })
        });
        
        const data = await response.json();
        hideLoading();
        
        if (data.success) {
            currentUser = data.user;
            showPage('dashboard');
            updateUserInfo();
            loadDashboard();
            showToast('Muvaffaqiyatli kirildi', 'success');
            startNotificationChecker();
        } else {
            showToast(data.error || 'Login xatosi', 'error');
        }
    } catch (error) {
        console.error('Login xatosi:', error);
        hideLoading();
        showToast('Server xatosi', 'error');
    }
}

async function handleLogout() {
    try {
        const response = await fetch('/api/logout', { method: 'POST' });
        const data = await response.json();
        
        if (data.success) {
            currentUser = null;
            showPage('login');
            showToast('Muvaffaqiyatli chiqildi', 'success');
            stopNotificationChecker();
        }
    } catch (error) {
        console.error('Logout xatosi:', error);
        showToast('Xatolik yuz berdi', 'error');
    }
}

// ==================== PAGE MANAGEMENT ====================
function showPage(pageId) {
    currentPage = pageId;
    
    // Barcha sahifalarni yashirish
    document.querySelectorAll('.page').forEach(page => {
        page.classList.remove('active');
    });
    
    // Kerakli sahifani ko'rsatish
    const pageElement = document.getElementById(pageId + 'Page');
    if (pageElement) {
        pageElement.classList.add('active');
        
        // Sahifa yuklanganda kerakli ma'lumotlarni yuklash
        switch(pageId) {
            case 'dashboard':
                loadDashboard();
                break;
            case 'users':
                loadUsers();
                break;
            case 'startups':
                loadStartups();
                break;
            case 'messages':
                loadMessageHistory();
                break;
            case 'statistics':
                loadDetailedStatistics();
                break;
            case 'admins':
                loadAdmins();
                break;
            case 'system':
                loadSystemHealth();
                break;
            case 'settings':
                loadSettings();
                break;
        }
    }
    
    // Mobil menuni yopish
    const sidebar = document.querySelector('.sidebar');
    if (sidebar && sidebar.classList.contains('active')) {
        sidebar.classList.remove('active');
    }
}

function setActiveMenuItem(pageId) {
    document.querySelectorAll('.menu li').forEach(item => {
        item.classList.remove('active');
    });
    
    const activeItem = document.querySelector(`.menu li[data-page="${pageId}"]`);
    if (activeItem) {
        activeItem.classList.add('active');
    }
}

function updateBreadcrumb(pageId) {
    const breadcrumb = document.querySelector('.breadcrumb');
    if (!breadcrumb) return;
    
    const pageNames = {
        'dashboard': 'Asosiy panel',
        'users': 'Foydalanuvchilar',
        'startups': 'Startaplar',
        'messages': 'Xabarlar',
        'statistics': 'Statistika',
        'admins': 'Adminlar',
        'system': 'Tizim holati',
        'settings': 'Sozlamalar'
    };
    
    breadcrumb.innerHTML = `
        <span class="breadcrumb-item">Boshqaruv paneli</span>
        <span class="breadcrumb-divider">/</span>
        <span class="breadcrumb-item active">${pageNames[pageId] || pageId}</span>
    `;
}

function updateUserInfo() {
    if (currentUser) {
        const adminName = document.getElementById('adminName');
        const adminEmail = document.getElementById('adminEmail');
        const adminAvatar = document.getElementById('adminAvatar');
        
        if (adminName) adminName.textContent = currentUser.full_name;
        if (adminEmail) adminEmail.textContent = currentUser.email || (currentUser.username + '@garajhub.uz');
        if (adminAvatar) adminAvatar.src = `https://ui-avatars.com/api/?name=${encodeURIComponent(currentUser.full_name)}&background=000&color=fff&bold=true`;
        
        // Role badge
        const roleBadge = document.getElementById('roleBadge');
        if (roleBadge) {
            roleBadge.textContent = currentUser.role === 'superadmin' ? 'Super Admin' : 'Admin';
            roleBadge.className = `role-badge ${currentUser.role}`;
        }
    }
}

// ==================== DASHBOARD FUNKSIYALARI ====================
async function loadDashboard() {
    try {
        showLoading();
        
        // Statistika
        const statsResponse = await fetch('/api/statistics');
        const statsData = await statsResponse.json();
        
        if (statsData.success) {
            updateStatistics(statsData.data);
        } else {
            showToast('Statistikani yuklashda xatolik', 'error');
        }
        
        // Grafiklar
        await loadUserGrowthChart();
        await loadStartupDistributionChart();
        
        // So'nggi faollik
        await loadRecentActivity();
        
        // Notificationlar
        await checkNewNotifications();
        
        hideLoading();
        
    } catch (error) {
        console.error('Dashboard yuklash xatosi:', error);
        hideLoading();
        showToast('Statistikani yuklashda xatolik', 'error');
    }
}

function updateStatistics(stats) {
    // Asosiy statistika
    updateElement('totalUsers', formatNumber(stats.total_users || 0));
    updateElement('totalStartups', formatNumber(stats.total_startups || 0));
    updateElement('activeStartups', formatNumber(stats.active_startups || 0));
    updateElement('newToday', formatNumber(stats.new_today || 0));
    
    // Faollik darajasi
    const activityRate = stats.active_users ? Math.round((stats.active_users / stats.total_users) * 100) : 0;
    updateElement('activityRate', activityRate + '%');
    const activityProgress = document.getElementById('activityProgress');
    if (activityProgress) {
        activityProgress.style.width = activityRate + '%';
    }
    
    // Trendlar
    const trendPercent = stats.trends?.users || '+0%';
    const trendElement = document.getElementById('startupTrend');
    if (trendElement) {
        const isPositive = trendPercent.includes('+');
        trendElement.innerHTML = `
            <i class="fas fa-arrow-${isPositive ? 'up' : 'down'}"></i>
            <span>${trendPercent}</span>
        `;
        trendElement.className = `trend ${isPositive ? 'positive' : 'negative'}`;
    }
    
    updateElement('activeStartupCount', `${stats.active_startups || 0} ta`);
    updateElement('newUsersToday', `${stats.new_today || 0} user`);
    
    // Kategoriyalar statistikasi
    if (stats.categories) {
        updateCategoryStats(stats.categories);
    }
}

function updateElement(id, value) {
    const element = document.getElementById(id);
    if (element) {
        element.textContent = value;
    }
}

function updateCategoryStats(categories) {
    const container = document.getElementById('categoryStats');
    if (!container) return;
    
    let html = '';
    Object.entries(categories).forEach(([category, count]) => {
        const percentage = Math.round((count / (Object.values(categories).reduce((a, b) => a + b, 0) || 1)) * 100);
        html += `
            <div class="category-item">
                <div class="category-info">
                    <span class="category-name">${category}</span>
                    <span class="category-count">${count}</span>
                </div>
                <div class="category-progress">
                    <div class="category-progress-bar" style="width: ${percentage}%"></div>
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html || '<div class="empty-state">Kategoriya statistikasi mavjud emas</div>';
}

async function loadUserGrowthChart() {
    try {
        const period = document.getElementById('growthFilter')?.value || 'month';
        const response = await fetch(`/api/analytics/user-growth?period=${period}`);
        const data = await response.json();
        
        if (data.success) {
            renderUserGrowthChart(data.data);
        }
    } catch (error) {
        console.error('Chart yuklash xatosi:', error);
    }
}

function renderUserGrowthChart(chartData) {
    const ctx = document.getElementById('userGrowthChart');
    if (!ctx) return;
    
    // Avvalgi chartni yo'q qilish
    if (userGrowthChart) {
        userGrowthChart.destroy();
    }
    
    // Yangi chart yaratish
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const textColor = isDark ? '#ffffff' : '#333333';
    const gridColor = isDark ? '#444444' : '#e0e0e0';
    
    userGrowthChart = new Chart(ctx, {
        type: 'line',
        data: chartData,
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        color: textColor,
                        font: {
                            family: "'Inter', sans-serif"
                        }
                    }
                },
                tooltip: {
                    backgroundColor: isDark ? '#2a2a2a' : '#ffffff',
                    titleColor: textColor,
                    bodyColor: textColor,
                    borderColor: gridColor,
                    borderWidth: 1,
                    padding: 10,
                    cornerRadius: 6
                }
            },
            scales: {
                x: {
                    grid: {
                        color: gridColor
                    },
                    ticks: {
                        color: textColor,
                        font: {
                            family: "'Inter', sans-serif"
                        }
                    }
                },
                y: {
                    beginAtZero: true,
                    grid: {
                        color: gridColor
                    },
                    ticks: {
                        color: textColor,
                        font: {
                            family: "'Inter', sans-serif"
                        }
                    }
                }
            },
            interaction: {
                intersect: false,
                mode: 'index'
            },
            animations: {
                tension: {
                    duration: 1000,
                    easing: 'linear'
                }
            }
        }
    });
}

async function loadStartupDistributionChart() {
    try {
        const response = await fetch('/api/analytics/startup-distribution');
        const data = await response.json();
        
        if (data.success) {
            renderStartupDistributionChart(data.data, data.total);
        }
    } catch (error) {
        console.error('Distribution chart xatosi:', error);
    }
}

function renderStartupDistributionChart(chartData, total) {
    const ctx = document.getElementById('startupDistributionChart');
    if (!ctx) return;
    
    // Avvalgi chartni yo'q qilish
    if (distributionChart) {
        distributionChart.destroy();
    }
    
    // Jami startaplar soni
    updateElement('totalStartupsChart', formatNumber(total || 0));
    
    // Legend yaratish
    const legendContainer = document.getElementById('distributionLegend');
    if (legendContainer) {
        let legendHTML = '';
        chartData.labels.forEach((label, index) => {
            const value = chartData.datasets[0].data[index];
            const colors = chartData.datasets[0].backgroundColor;
            legendHTML += `
                <div class="legend-item">
                    <div class="legend-color" style="background-color: ${colors[index]}"></div>
                    <div class="legend-text">${label}</div>
                    <div class="legend-value">${formatNumber(value)}</div>
                </div>
            `;
        });
        legendContainer.innerHTML = legendHTML;
    }
    
    // Yangi chart yaratish
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    
    distributionChart = new Chart(ctx, {
        type: 'doughnut',
        data: chartData,
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '70%',
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: isDark ? '#2a2a2a' : '#ffffff',
                    titleColor: isDark ? '#ffffff' : '#333333',
                    bodyColor: isDark ? '#ffffff' : '#333333',
                    borderColor: isDark ? '#444444' : '#e0e0e0',
                    borderWidth: 1,
                    padding: 10,
                    cornerRadius: 6
                }
            },
            animation: {
                animateScale: true,
                animateRotate: true
            }
        }
    });
}

async function loadRecentActivity() {
    try {
        const activityList = document.getElementById('activityList');
        if (!activityList) return;
        
        const response = await fetch('/api/notifications');
        const data = await response.json();
        
        if (data.success && data.data.length > 0) {
            let html = '';
            data.data.slice(0, 10).forEach(notification => {
                const icon = notification.type === 'new_startup' ? 'fa-rocket' : 
                            notification.type === 'new_user' ? 'fa-user' : 'fa-bell';
                
                html += `
                    <div class="activity-item">
                        <div class="activity-icon">
                            <i class="fas ${icon}"></i>
                        </div>
                        <div class="activity-content">
                            <div class="activity-title">${notification.title}</div>
                            <div class="activity-time">${notification.timestamp}</div>
                        </div>
                    </div>
                `;
            });
            
            activityList.innerHTML = html;
        } else {
            activityList.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-history"></i>
                    <p>Faollik tarixi hozircha bo'sh</p>
                </div>
            `;
        }
        
    } catch (error) {
        console.error('Activity yuklash xatosi:', error);
    }
}

function filterActivity(type) {
    const buttons = document.querySelectorAll('.activity-filter-btn');
    buttons.forEach(btn => btn.classList.remove('active'));
    event.target.classList.add('active');
    
    // Bu joyda faollikni filtrlash logikasi
    console.log('Faollik filtrlandi:', type);
    loadRecentActivity();
}

// ==================== USERS FUNKSIYALARI ====================
async function loadUsers(page = 1) {
    try {
        showLoading();
        const search = document.getElementById('userSearch')?.value || '';
        const filter = document.getElementById('userFilter')?.value || 'all';
        
        const response = await fetch(`/api/users?page=${page}&search=${encodeURIComponent(search)}&filter=${filter}`);
        const data = await response.json();
        
        hideLoading();
        
        if (data.success) {
            updateUsersTable(data.data);
            updatePagination('usersPagination', data.pagination, loadUsers);
        } else {
            showToast(data.error || 'Foydalanuvchilarni yuklashda xatolik', 'error');
        }
    } catch (error) {
        console.error('Foydalanuvchilar yuklash xatosi:', error);
        hideLoading();
        showToast('Foydalanuvchilarni yuklashda xatolik', 'error');
    }
}

function updateUsersTable(users) {
    const tbody = document.getElementById('usersTableBody');
    if (!tbody) return;
    
    if (users.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" style="text-align: center; padding: 40px;">
                    <i class="fas fa-users" style="font-size: 32px; color: var(--text-muted); margin-bottom: 10px; display: block;"></i>
                    <p style="color: var(--text-muted);">Foydalanuvchilar topilmadi</p>
                </td>
            </tr>
        `;
        return;
    }
    
    let html = '';
    users.forEach(user => {
        const statusClass = user.status === 'active' ? 'active' : 'inactive';
        const statusText = user.status === 'active' ? 'Faol' : 'Faol emas';
        
        html += `
            <tr>
                <td>${user.user_id || user.id}</td>
                <td><strong>${user.first_name} ${user.last_name || ''}</strong></td>
                <td>${user.username || '-'}</td>
                <td>${user.phone || '+998 ** *** ** **'}</td>
                <td>${formatDate(user.joined_at)}</td>
                <td>
                    <span class="status-badge ${statusClass}">${statusText}</span>
                </td>
                <td>
                    <div class="table-actions">
                        <button class="action-btn view-btn" onclick="viewUser('${user.user_id || user.id}')" title="Ko'rish">
                            <i class="fas fa-eye"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    });
    
    tbody.innerHTML = html;
}

async function viewUser(userId) {
    try {
        showLoading();
        const response = await fetch(`/api/users/${userId}`);
        const data = await response.json();
        
        hideLoading();
        
        if (data.success) {
            showUserDetailModal(data.data);
        } else {
            showToast(data.error || 'Foydalanuvchi ma\'lumotlari topilmadi', 'error');
        }
    } catch (error) {
        console.error('Foydalanuvchi ma\'lumotlari xatosi:', error);
        hideLoading();
        showToast('Foydalanuvchi ma\'lumotlarini yuklashda xatolik', 'error');
    }
}

function showUserDetailModal(user) {
    const modalContent = document.getElementById('userDetailContent');
    
    if (modalContent) {
        modalContent.innerHTML = `
            <div class="user-details">
                <div class="user-header">
                    <img src="https://ui-avatars.com/api/?name=${encodeURIComponent(user.first_name + ' ' + (user.last_name || ''))}&background=000&color=fff" 
                         alt="${user.first_name}" class="user-detail-avatar">
                    <div>
                        <h4>${user.first_name} ${user.last_name || ''}</h4>
                        <p class="user-detail-email">${user.phone || 'Telefon mavjud emas'}</p>
                        <p class="user-detail-id">ID: ${user.id}</p>
                    </div>
                </div>
                
                <div class="user-info-grid">
                    <div class="info-item">
                        <span class="info-label">Username:</span>
                        <span class="info-value">${user.username || 'Mavjud emas'}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Telefon:</span>
                        <span class="info-value">${user.phone || 'Mavjud emas'}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Mutaxassislik:</span>
                        <span class="info-value">${user.specialization || 'Kiritilmagan'}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Tajriba:</span>
                        <span class="info-value">${user.experience || 'Kiritilmagan'}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Jinsi:</span>
                        <span class="info-value">${user.gender || 'Kiritilmagan'}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Tug'ilgan sana:</span>
                        <span class="info-value">${user.birth_date || 'Kiritilmagan'}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Ro'yxatdan o'tgan:</span>
                        <span class="info-value">${formatDate(user.joined_at)}</span>
                    </div>
                </div>
                
                <div class="stats-section">
                    <h5>Statistika</h5>
                    <div class="stats-grid">
                        <div class="stat-item">
                            <span class="stat-label">Yaratgan startaplar</span>
                            <span class="stat-value">${user.stats?.created || 0}</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">Qo'shilgan startaplar</span>
                            <span class="stat-value">${user.stats?.joined || 0}</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">Faol startaplar</span>
                            <span class="stat-value">${user.stats?.active || 0}</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">Yakunlangan</span>
                            <span class="stat-value">${user.stats?.completed || 0}</span>
                        </div>
                    </div>
                </div>
                
                ${user.startups && user.startups.length > 0 ? `
                    <div class="startup-list">
                        <h5>Yaratgan startaplar (${user.startups.length})</h5>
                        <div class="startup-list-container">
                            ${user.startups.map(startup => `
                                <div class="startup-item">
                                    <div class="startup-item-header">
                                        <strong>${startup.name}</strong>
                                        <span class="status-badge ${startup.status}">${startup.status}</span>
                                    </div>
                                    <div class="startup-item-meta">${formatDate(startup.created_at)}</div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}
            </div>
        `;
        
        openModal('userDetailModal');
    }
}

// ==================== STARTUPS FUNKSIYALARI ====================
async function loadStartups(page = 1) {
    try {
        showLoading();
        const search = document.getElementById('startupSearch')?.value || '';
        const status = document.getElementById('startupFilter')?.value || 'all';
        const category = document.getElementById('startupCategoryFilter')?.value || 'all';
        
        const response = await fetch(`/api/startups?page=${page}&search=${encodeURIComponent(search)}&status=${status}&category=${category}`);
        const data = await response.json();
        
        hideLoading();
        
        if (data.success) {
            updateStartupsTable(data.data);
            updatePagination('startupsPagination', data.pagination, loadStartups);
        } else {
            showToast(data.error || 'Startaplarni yuklashda xatolik', 'error');
        }
    } catch (error) {
        console.error('Startaplar yuklash xatosi:', error);
        hideLoading();
        showToast('Startaplarni yuklashda xatolik', 'error');
    }
}

function updateStartupsTable(startups) {
    const tbody = document.getElementById('startupsTableBody');
    if (!tbody) return;
    
    if (startups.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" style="text-align: center; padding: 40px;">
                    <i class="fas fa-rocket" style="font-size: 32px; color: var(--text-muted); margin-bottom: 10px; display: block;"></i>
                    <p style="color: var(--text-muted);">Startaplar topilmadi</p>
                </td>
            </tr>
        `;
        return;
    }
    
    let html = '';
    startups.forEach(startup => {
        const statusClass = startup.status;
        const statusText = startup.status_text || startup.status;
        
        html += `
            <tr>
                <td>${startup.id.slice(-6)}</td>
                <td><strong>${startup.name}</strong></td>
                <td>${startup.owner_name}</td>
                <td><span class="status-badge ${statusClass}">${statusText}</span></td>
                <td>${formatDate(startup.created_at)}</td>
                <td>${startup.member_count || 1}/${startup.max_members || 10}</td>
                <td>
                    <div class="table-actions">
                        <button class="action-btn view-btn" onclick="viewStartup('${startup.id}')" title="Ko'rish">
                            <i class="fas fa-eye"></i>
                        </button>
                        ${startup.status === 'pending' ? `
                            <button class="action-btn edit-btn" onclick="approveStartup('${startup.id}')" title="Tasdiqlash">
                                <i class="fas fa-check"></i>
                            </button>
                            <button class="action-btn delete-btn" onclick="rejectStartup('${startup.id}')" title="Rad etish">
                                <i class="fas fa-times"></i>
                            </button>
                        ` : ''}
                        ${startup.status === 'active' ? `
                            <button class="action-btn edit-btn" onclick="completeStartup('${startup.id}')" title="Yakunlash">
                                <i class="fas fa-flag-checkered"></i>
                            </button>
                        ` : ''}
                    </div>
                </td>
            </tr>
        `;
    });
    
    tbody.innerHTML = html;
}

async function viewStartup(startupId) {
    try {
        showLoading();
        const response = await fetch(`/api/startup/${startupId}`);
        const data = await response.json();
        
        hideLoading();
        
        if (data.success) {
            showStartupDetailModal(data.data);
        } else {
            showToast(data.error || 'Startap ma\'lumotlari topilmadi', 'error');
        }
    } catch (error) {
        console.error('Startap ma\'lumotlari xatosi:', error);
        hideLoading();
        showToast('Startap ma\'lumotlarini yuklashda xatolik', 'error');
    }
}

function showStartupDetailModal(startup) {
    const modalContent = document.getElementById('startupDetailContent');
    
    if (modalContent) {
        modalContent.innerHTML = `
            <div class="startup-details">
                <div class="startup-header">
                    ${startup.logo ? `
                        <img src="${startup.logo}" alt="${startup.name}" class="startup-logo">
                    ` : `
                        <div class="startup-logo-placeholder">
                            <i class="fas fa-rocket"></i>
                        </div>
                    `}
                    <div>
                        <h4>${startup.name}</h4>
                        <p class="startup-meta">
                            <span class="status-badge ${startup.status}">${startup.status_text}</span>
                            <span class="startup-category">${startup.category || 'Boshqa'}</span>
                        </p>
                    </div>
                </div>
                
                <div class="startup-info-grid">
                    <div class="info-item">
                        <span class="info-label">ID:</span>
                        <span class="info-value">${startup.id}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Yaratilgan sana:</span>
                        <span class="info-value">${formatDate(startup.created_at)}</span>
                    </div>
                    ${startup.started_at ? `
                        <div class="info-item">
                            <span class="info-label">Boshlangan sana:</span>
                            <span class="info-value">${formatDate(startup.started_at)}</span>
                        </div>
                    ` : ''}
                    ${startup.ended_at ? `
                        <div class="info-item">
                            <span class="info-label">Yakunlangan sana:</span>
                            <span class="info-value">${formatDate(startup.ended_at)}</span>
                        </div>
                    ` : ''}
                    <div class="info-item">
                        <span class="info-label">A'zolar:</span>
                        <span class="info-value">${startup.member_count || 0}/${startup.max_members || 10}</span>
                    </div>
                    ${startup.group_link ? `
                        <div class="info-item">
                            <span class="info-label">Guruh havolasi:</span>
                            <span class="info-value">
                                <a href="${startup.group_link}" target="_blank" class="external-link">
                                    <i class="fas fa-external-link-alt"></i> Havola
                                </a>
                            </span>
                        </div>
                    ` : ''}
                </div>
                
                <div class="description-section">
                    <h5>Tavsif:</h5>
                    <p class="description-text">${startup.description || 'Tavsif mavjud emas'}</p>
                </div>
                
                ${startup.required_skills ? `
                    <div class="skills-section">
                        <h5>Kerakli mutaxassislar:</h5>
                        <p class="skills-text">${startup.required_skills}</p>
                    </div>
                ` : ''}
                
                ${startup.results ? `
                    <div class="results-section">
                        <h5>Natijalar:</h5>
                        <p class="results-text">${startup.results}</p>
                    </div>
                ` : ''}
                
                ${startup.owner ? `
                    <div class="owner-section">
                        <h5>Muallif:</h5>
                        <div class="owner-info">
                            <img src="https://ui-avatars.com/api/?name=${encodeURIComponent(startup.owner.first_name + ' ' + (startup.owner.last_name || ''))}&background=000&color=fff" 
                                 alt="${startup.owner.first_name}" class="owner-avatar">
                            <div>
                                <p class="owner-name">${startup.owner.first_name} ${startup.owner.last_name || ''}</p>
                                <p class="owner-contact">${startup.owner.phone || 'Telefon mavjud emas'}</p>
                                ${startup.owner.username ? `<p class="owner-username">@${startup.owner.username}</p>` : ''}
                            </div>
                        </div>
                    </div>
                ` : ''}
                
                ${startup.members && startup.members.length > 0 ? `
                    <div class="members-section">
                        <h5>A'zolar (${startup.members.length}):</h5>
                        <div class="members-list">
                            ${startup.members.map(member => `
                                <div class="member-item">
                                    <div class="member-info">
                                        <img src="https://ui-avatars.com/api/?name=${encodeURIComponent(member.first_name + ' ' + (member.last_name || ''))}&background=000&color=fff" 
                                             alt="${member.first_name}" class="member-avatar">
                                        <span class="member-name">${member.first_name} ${member.last_name || ''}</span>
                                    </div>
                                    <span class="member-role">${member.role || 'A\'zo'}</span>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}
                
                ${startup.join_requests && startup.join_requests.length > 0 ? `
                    <div class="join-requests-section">
                        <h5>Join Requests (${startup.join_requests.length}):</h5>
                        <div class="join-requests-list">
                            ${startup.join_requests.map(request => `
                                <div class="join-request-item">
                                    <div class="join-request-info">
                                        <span class="join-request-user">User ID: ${request.user_id}</span>
                                        <span class="join-request-status">Status: ${request.status}</span>
                                    </div>
                                    <span class="join-request-time">${formatDate(request.created_at)}</span>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}
            </div>
        `;
        
        openModal('startupDetailModal');
    }
}

async function approveStartup(startupId) {
    if (!confirm('Startapni tasdiqlaysizmi?')) {
        return;
    }
    
    try {
        showLoading();
        const response = await fetch(`/api/startup/${startupId}/approve`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        hideLoading();
        
        if (data.success) {
            showToast('Startap tasdiqlandi', 'success');
            loadStartups();
            loadDashboard();
        } else {
            showToast(data.error || 'Tasdiqlash xatosi', 'error');
        }
    } catch (error) {
        console.error('Tasdiqlash xatosi:', error);
        hideLoading();
        showToast('Server xatosi', 'error');
    }
}

async function rejectStartup(startupId) {
    if (!confirm('Startapni rad etasizmi?')) {
        return;
    }
    
    const reason = prompt('Rad etish sababini kiriting:');
    if (!reason) {
        showToast('Sabab kiritilmadi', 'warning');
        return;
    }
    
    try {
        showLoading();
        const response = await fetch(`/api/startup/${startupId}/reject`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ reason })
        });
        
        const data = await response.json();
        hideLoading();
        
        if (data.success) {
            showToast('Startap rad etildi', 'success');
            loadStartups();
        } else {
            showToast(data.error || 'Rad etish xatosi', 'error');
        }
    } catch (error) {
        console.error('Rad etish xatosi:', error);
        hideLoading();
        showToast('Server xatosi', 'error');
    }
}

async function completeStartup(startupId) {
    const results = prompt('Startap natijalarini kiriting:');
    if (!results) {
        showToast('Natijalar kiritilmadi', 'warning');
        return;
    }
    
    try {
        showLoading();
        const response = await fetch(`/api/startup/${startupId}/complete`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ results })
        });
        
        const data = await response.json();
        hideLoading();
        
        if (data.success) {
            showToast('Startap yakunlandi', 'success');
            loadStartups();
        } else {
            showToast(data.error || 'Yakunlash xatosi', 'error');
        }
    } catch (error) {
        console.error('Yakunlash xatosi:', error);
        hideLoading();
        showToast('Server xatosi', 'error');
    }
}

// ==================== MESSAGES FUNKSIYALARI ====================
async function handleBroadcast(e) {
    e.preventDefault();
    
    const message = document.getElementById('messageText').value;
    const recipientType = document.getElementById('messageType').value;
    
    if (!message.trim()) {
        showToast('Xabar matnini kiriting', 'error');
        return;
    }
    
    try {
        showLoading();
        const response = await fetch('/api/broadcast', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message,
                recipient_type: recipientType
            })
        });
        
        const data = await response.json();
        hideLoading();
        
        if (data.success) {
            showToast('Xabar yuborildi', 'success');
            clearMessageForm();
            loadMessageHistory();
        } else {
            showToast(data.error || 'Xabar yuborish xatosi', 'error');
        }
    } catch (error) {
        console.error('Xabar yuborish xatosi:', error);
        hideLoading();
        showToast('Server xatosi', 'error');
    }
}

async function handleBroadcastModal(e) {
    e.preventDefault();
    
    const message = document.getElementById('modalMessageText').value;
    const recipientType = document.getElementById('modalMessageType').value;
    
    if (!message.trim()) {
        showToast('Xabar matnini kiriting', 'error');
        return;
    }
    
    try {
        showLoading();
        const response = await fetch('/api/broadcast', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message,
                recipient_type: recipientType
            })
        });
        
        const data = await response.json();
        hideLoading();
        
        if (data.success) {
            showToast('Xabar yuborildi', 'success');
            closeModal();
            loadMessageHistory();
        } else {
            showToast(data.error || 'Xabar yuborish xatosi', 'error');
        }
    } catch (error) {
        console.error('Xabar yuborish xatosi:', error);
        hideLoading();
        showToast('Server xatosi', 'error');
    }
}

async function loadMessageHistory() {
    try {
        const historyList = document.getElementById('messageHistory');
        if (!historyList) return;
        
        // API orqali yuborilgan xabarlarni olish
        historyList.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-history"></i>
                <p>Xabar tarixi hozircha bo'sh</p>
            </div>
        `;
        
    } catch (error) {
        console.error('Xabarlar yuklash xatosi:', error);
    }
}

function clearMessageForm() {
    document.getElementById('messageText').value = '';
    document.getElementById('messageType').value = 'all';
}

function openBroadcastModal() {
    document.getElementById('modalMessageText').value = '';
    document.getElementById('modalMessageType').value = 'all';
    openModal('broadcastModal');
}

// ==================== STATISTICS FUNKSIYALARI ====================
async function loadDetailedStatistics() {
    try {
        showLoading();
        const period = document.getElementById('statsPeriod')?.value || 'month';
        
        // Statistika ma'lumotlarini yuklash
        const statsResponse = await fetch('/api/statistics');
        const statsData = await statsResponse.json();
        
        if (statsData.success) {
            updateDetailedStatistics(statsData.data);
        }
        
        // Kategoriyalar statistikasi
        const categoriesResponse = await fetch('/api/categories');
        const categoriesData = await categoriesResponse.json();
        
        if (categoriesData.success) {
            updateCategoriesChart(categoriesData.data);
        }
        
        // Faollik grafigi
        renderActivityChart();
        
        hideLoading();
        
    } catch (error) {
        console.error('Batafsil statistika xatosi:', error);
        hideLoading();
        showToast('Statistikani yuklashda xatolik', 'error');
    }
}

function updateDetailedStatistics(stats) {
    // Foydalanuvchi statistikasi
    updateElement('detailedTotalUsers', formatNumber(stats.total_users || 0));
    updateElement('detailedActiveUsers', formatNumber(stats.active_users || 0));
    updateElement('detailedNewUsers', formatNumber(stats.new_today || 0));
    
    const avgDailyUsers = stats.total_users ? Math.round(stats.total_users / 30) : 0;
    updateElement('detailedAvgDailyUsers', formatNumber(avgDailyUsers));
    
    // Startap statistikasi
    updateElement('detailedTotalStartups', formatNumber(stats.total_startups || 0));
    updateElement('detailedActiveStartups', formatNumber(stats.active_startups || 0));
    updateElement('detailedNewStartups', formatNumber(stats.pending_startups || 0));
    
    const successRate = stats.total_startups > 0 ? 
        Math.round((stats.completed_startups / stats.total_startups) * 100) : 0;
    updateElement('detailedSuccessRate', successRate + '%');
}

function updateCategoriesChart(categories) {
    const container = document.getElementById('categoriesChart');
    if (!container) return;
    
    if (categories.length === 0) {
        container.innerHTML = '<div class="empty-state">Kategoriya statistikasi mavjud emas</div>';
        return;
    }
    
    // Top 10 kategoriyalar
    const topCategories = categories.slice(0, 10);
    
    let html = '';
    topCategories.forEach(category => {
        const total = category.total || 0;
        const active = category.active || 0;
        const completed = category.completed || 0;
        
        html += `
            <div class="category-chart-item">
                <div class="category-name">${category.name}</div>
                <div class="category-stats">
                    <div class="category-stat">
                        <span class="stat-label">Jami:</span>
                        <span class="stat-value">${total}</span>
                    </div>
                    <div class="category-stat">
                        <span class="stat-label">Faol:</span>
                        <span class="stat-value">${active}</span>
                    </div>
                    <div class="category-stat">
                        <span class="stat-label">Yakunlangan:</span>
                        <span class="stat-value">${completed}</span>
                    </div>
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

function renderActivityChart() {
    const ctx = document.getElementById('activityChart');
    if (!ctx) return;
    
    // Avvalgi chartni yo'q qilish
    if (activityChart) {
        activityChart.destroy();
    }
    
    // Bo'sh chart yaratish (keyin API orqali to'ldiriladi)
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const textColor = isDark ? '#ffffff' : '#333333';
    const gridColor = isDark ? '#444444' : '#e0e0e0';
    
    activityChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Dushanba', 'Seshanba', 'Chorshanba', 'Payshanba', 'Juma', 'Shanba', 'Yakshanba'],
            datasets: [{
                label: 'Faol startaplar',
                data: [12, 19, 8, 15, 12, 5, 18],
                backgroundColor: 'rgba(0, 0, 0, 0.7)',
                borderColor: '#000000',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    labels: {
                        color: textColor
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        color: gridColor
                    },
                    ticks: {
                        color: textColor
                    }
                },
                y: {
                    beginAtZero: true,
                    grid: {
                        color: gridColor
                    },
                    ticks: {
                        color: textColor
                    }
                }
            }
        }
    });
}

// ==================== SYSTEM HEALTH FUNKSIYALARI ====================
async function loadSystemHealth() {
    try {
        showLoading();
        const response = await fetch('/api/system/health');
        const data = await response.json();
        
        hideLoading();
        
        if (data.success) {
            updateSystemHealth(data.data);
        } else {
            showToast('Tizim holatini yuklashda xatolik', 'error');
        }
    } catch (error) {
        console.error('Tizim holati xatosi:', error);
        hideLoading();
        showToast('Tizim holatini yuklashda xatolik', 'error');
    }
}

function updateSystemHealth(healthData) {
    // CPU
    updateElement('cpuUsage', healthData.cpu.usage + '%');
    updateElement('cpuCores', healthData.cpu.cores);
    const cpuProgress = document.getElementById('cpuProgress');
    if (cpuProgress) {
        cpuProgress.style.width = healthData.cpu.usage + '%';
        cpuProgress.className = `progress-bar ${getHealthStatusClass(healthData.cpu.status)}`;
    }
    
    // Memory
    const memoryUsage = formatBytes(healthData.memory.used) + ' / ' + formatBytes(healthData.memory.total);
    updateElement('memoryUsage', memoryUsage);
    updateElement('memoryPercent', healthData.memory.percent + '%');
    const memoryProgress = document.getElementById('memoryProgress');
    if (memoryProgress) {
        memoryProgress.style.width = healthData.memory.percent + '%';
        memoryProgress.className = `progress-bar ${getHealthStatusClass(healthData.memory.status)}`;
    }
    
    // Disk
    const diskUsage = formatBytes(healthData.disk.used) + ' / ' + formatBytes(healthData.disk.total);
    updateElement('diskUsage', diskUsage);
    updateElement('diskPercent', healthData.disk.percent + '%');
    const diskProgress = document.getElementById('diskProgress');
    if (diskProgress) {
        diskProgress.style.width = healthData.disk.percent + '%';
        diskProgress.className = `progress-bar ${getHealthStatusClass(healthData.disk.status)}`;
    }
    
    // Xizmatlar holati
    updateServiceStatus(healthData.services);
    
    // Uptime
    const uptimeElement = document.getElementById('uptime');
    if (uptimeElement) {
        uptimeElement.textContent = formatUptime(healthData.uptime);
    }
}

function getHealthStatusClass(status) {
    switch(status) {
        case 'good': return 'good';
        case 'warning': return 'warning';
        case 'critical': return 'critical';
        default: return '';
    }
}

function updateServiceStatus(services) {
    // Bot holati
    const botStatusDot = document.getElementById('botStatusDot');
    const botStatusText = document.getElementById('botStatusText');
    const botStatusBadge = document.getElementById('botStatusBadge');
    
    if (botStatusDot && botStatusText) {
        if (services.bot === 'online') {
            botStatusDot.className = 'status-dot online';
            botStatusText.textContent = 'Online';
            if (botStatusBadge) {
                botStatusBadge.textContent = 'Online';
                botStatusBadge.className = 'status-badge active';
            }
        } else {
            botStatusDot.className = 'status-dot offline';
            botStatusText.textContent = 'Offline';
            if (botStatusBadge) {
                botStatusBadge.textContent = 'Offline';
                botStatusBadge.className = 'status-badge rejected';
            }
        }
    }
    
    // Database holati
    const dbStatusDot = document.getElementById('dbStatusDot');
    const dbStatusText = document.getElementById('dbStatusText');
    
    if (dbStatusDot && dbStatusText) {
        if (services.database === 'online') {
            dbStatusDot.className = 'status-dot online';
            dbStatusText.textContent = 'Online';
        } else {
            dbStatusDot.className = 'status-dot offline';
            dbStatusText.textContent = 'Offline';
        }
    }
    
    // Web server holati
    const webStatusDot = document.getElementById('webStatusDot');
    const webStatusText = document.getElementById('webStatusText');
    
    if (webStatusDot && webStatusText) {
        if (services.web_server === 'online') {
            webStatusDot.className = 'status-dot online';
            webStatusText.textContent = 'Online';
        } else {
            webStatusDot.className = 'status-dot offline';
            webStatusText.textContent = 'Offline';
        }
    }
}

// ==================== SETTINGS FUNKSIYALARI ====================
async function loadSettings() {
    try {
        showLoading();
        const response = await fetch('/api/settings');
        const data = await response.json();
        
        hideLoading();
        
        if (data.success) {
            updateSettingsForm(data.data);
        } else {
            showToast('Sozlamalarni yuklashda xatolik', 'error');
        }
    } catch (error) {
        console.error('Sozlamalar yuklash xatosi:', error);
        hideLoading();
        showToast('Sozlamalarni yuklashda xatolik', 'error');
    }
}

function updateSettingsForm(settings) {
    // Umumiy sozlamalar
    updateFormValue('siteName', settings.site_name);
    updateFormValue('adminEmail', settings.admin_email);
    updateFormValue('timezone', settings.timezone);
    
    // Bot sozlamalari
    updateElement('botToken', settings.bot_token);
    updateElement('channelUsername', settings.channel_username);
    updateElement('adminId', settings.admin_id);
    updateElement('version', settings.version);
    
    const botStatusBadge = document.getElementById('botStatusBadge');
    if (botStatusBadge) {
        if (settings.bot_status === 'online') {
            botStatusBadge.textContent = 'Online';
            botStatusBadge.className = 'status-badge active';
        } else {
            botStatusBadge.textContent = 'Offline';
            botStatusBadge.className = 'status-badge rejected';
        }
    }
    
    const dbStatusBadge = document.getElementById('dbStatusBadge');
    if (dbStatusBadge) {
        if (settings.db_status === 'online') {
            dbStatusBadge.textContent = 'Online';
            dbStatusBadge.className = 'status-badge active';
        } else {
            dbStatusBadge.textContent = 'Offline';
            dbStatusBadge.className = 'status-badge rejected';
        }
    }
}

function updateFormValue(id, value) {
    const element = document.getElementById(id);
    if (element) {
        element.value = value || '';
    }
}

async function handleSettingsSave(e) {
    e.preventDefault();
    
    const settings = {
        site_name: document.getElementById('siteName').value,
        admin_email: document.getElementById('adminEmail').value,
        timezone: document.getElementById('timezone').value
    };
    
    try {
        showLoading();
        const response = await fetch('/api/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(settings)
        });
        
        const data = await response.json();
        hideLoading();
        
        if (data.success) {
            showToast('Sozlamalar saqlandi', 'success');
        } else {
            showToast(data.error || 'Sozlamalarni saqlash xatosi', 'error');
        }
    } catch (error) {
        console.error('Sozlamalar xatosi:', error);
        hideLoading();
        showToast('Server xatosi', 'error');
    }
}

function saveNotificationSettings() {
    const notifyNewUsers = document.getElementById('notifyNewUsers').checked;
    const notifyNewStartups = document.getElementById('notifyNewStartups').checked;
    const notifyStartupApproval = document.getElementById('notifyStartupApproval').checked;
    
    // Bu yerda sozlamalarni saqlash logikasi
    localStorage.setItem('notifyNewUsers', notifyNewUsers);
    localStorage.setItem('notifyNewStartups', notifyNewStartups);
    localStorage.setItem('notifyStartupApproval', notifyStartupApproval);
    
    showToast('Bildirishnoma sozlamalari saqlandi', 'success');
}

// ==================== UTILITY FUNKSIYALARI ====================
function openModal(modalId) {
    const modalOverlay = document.getElementById('modalOverlay');
    const modal = document.getElementById(modalId);
    
    if (modalOverlay && modal) {
        modalOverlay.classList.add('active');
        modal.style.display = 'block';
        document.body.style.overflow = 'hidden';
    }
}

function closeModal() {
    const modalOverlay = document.getElementById('modalOverlay');
    
    if (modalOverlay) {
        modalOverlay.classList.remove('active');
        modalOverlay.querySelectorAll('.modal').forEach(modal => {
            modal.style.display = 'none';
        });
        document.body.style.overflow = 'auto';
    }
}

function showToast(message, type = 'info') {
    const colors = {
        success: '#000000',
        error: '#ff4444',
        warning: '#ff8800',
        info: '#0099cc'
    };
    
    Toastify({
        text: message,
        duration: 3000,
        gravity: "top",
        position: "right",
        backgroundColor: colors[type] || colors.info,
        stopOnFocus: true,
        style: {
            fontFamily: "'Inter', sans-serif",
            fontWeight: '500',
            borderRadius: '8px',
            padding: '12px 20px',
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)'
        }
    }).showToast();
}

function showLoading() {
    const loading = document.getElementById('loadingScreen');
    if (loading) {
        loading.style.display = 'flex';
        loading.style.opacity = '1';
    }
}

function hideLoading() {
    const loading = document.getElementById('loadingScreen');
    if (loading) {
        loading.style.opacity = '0';
        setTimeout(() => {
            loading.style.display = 'none';
        }, 300);
    }
}

function toggleTheme() {
    const theme = this.checked ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
    
    // Grafiklarni yangilash
    setTimeout(() => {
        if (currentPage === 'dashboard') {
            if (userGrowthChart) {
                userGrowthChart.destroy();
                loadUserGrowthChart();
            }
            if (distributionChart) {
                distributionChart.destroy();
                loadStartupDistributionChart();
            }
        }
        if (currentPage === 'statistics' && activityChart) {
            activityChart.destroy();
            renderActivityChart();
        }
    }, 100);
}

function formatDate(dateString) {
    if (!dateString) return 'Noma\'lum';
    
    try {
        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);
        
        if (diffMins < 1) return 'Hozirgina';
        if (diffMins < 60) return `${diffMins} daqiqa oldin`;
        if (diffHours < 24) return `${diffHours} soat oldin`;
        if (diffDays === 1) return 'Kecha';
        if (diffDays < 7) return `${diffDays} kun oldin`;
        
        return date.toLocaleDateString('uz-UZ', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch (error) {
        return dateString;
    }
}

function formatNumber(num) {
    if (typeof num !== 'number') {
        num = parseInt(num) || 0;
    }
    return new Intl.NumberFormat('uz-UZ').format(num);
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatUptime(seconds) {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    
    let result = '';
    if (days > 0) result += `${days} kun `;
    if (hours > 0) result += `${hours} soat `;
    if (minutes > 0) result += `${minutes} daqiqa`;
    
    return result || 'Bir necha soniya';
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function updatePagination(elementId, pagination, callback) {
    const container = document.getElementById(elementId);
    if (!container) return;
    
    const { page, per_page, total, total_pages } = pagination;
    
    if (total_pages <= 1) {
        container.innerHTML = '';
        return;
    }
    
    let html = `
        <button class="pagination-btn" ${page === 1 ? 'disabled' : ''} onclick="${callback.name}(${page - 1})">
            <i class="fas fa-chevron-left"></i>
        </button>
        
        <div class="page-numbers">
    `;
    
    // Page numbers
    const maxVisible = 5;
    let startPage = Math.max(1, page - Math.floor(maxVisible / 2));
    let endPage = Math.min(total_pages, startPage + maxVisible - 1);
    
    if (endPage - startPage + 1 < maxVisible) {
        startPage = Math.max(1, endPage - maxVisible + 1);
    }
    
    for (let i = startPage; i <= endPage; i++) {
        html += `
            <button class="pagination-btn ${i === page ? 'active' : ''}" onclick="${callback.name}(${i})">
                ${i}
            </button>
        `;
    }
    
    html += `
        </div>
        
        <button class="pagination-btn" ${page === total_pages ? 'disabled' : ''} onclick="${callback.name}(${page + 1})">
            <i class="fas fa-chevron-right"></i>
        </button>
    `;
    
    container.innerHTML = html;
}

function handleSearch(e) {
    const query = e.target.value.trim();
    if (query.length < 2) {
        document.getElementById('searchResults').style.display = 'none';
        return;
    }
    
    // Qidiruv natijalarini ko'rsatish
    document.getElementById('searchResults').style.display = 'block';
    document.getElementById('searchResults').innerHTML = `
        <div class="search-result-item" onclick="showPage('users')">
            <div class="search-result-icon">
                <i class="fas fa-user"></i>
            </div>
            <div class="search-result-content">
                <div class="search-result-title">Foydalanuvchilar qidiruvi</div>
                <div class="search-result-subtitle">"${query}" so'zini o'z ichiga olgan foydalanuvchilar</div>
            </div>
        </div>
        <div class="search-result-item" onclick="showPage('startups')">
            <div class="search-result-icon">
                <i class="fas fa-rocket"></i>
            </div>
            <div class="search-result-content">
                <div class="search-result-title">Startaplar qidiruvi</div>
                <div class="search-result-subtitle">"${query}" so'zini o'z ichiga olgan startaplar</div>
            </div>
        </div>
    `;
}

async function showNotifications() {
    try {
        const response = await fetch('/api/notifications');
        const data = await response.json();
        
        if (data.success) {
            const notificationCount = document.getElementById('notificationCount');
            if (notificationCount) {
                notificationCount.textContent = data.data.length;
                notificationCount.style.display = data.data.length > 0 ? 'block' : 'none';
            }
            
            // Notification dropdown yaratish
            createNotificationDropdown(data.data);
        }
    } catch (error) {
        console.error('Notificationlar yuklash xatosi:', error);
    }
}

function createNotificationDropdown(notifications) {
    const dropdown = document.getElementById('notificationDropdown');
    if (!dropdown) return;
    
    if (notifications.length === 0) {
        dropdown.innerHTML = '<div class="notification-empty">Yangi bildirishnomalar yo\'q</div>';
        return;
    }
    
    let html = '';
    notifications.slice(0, 5).forEach(notification => {
        const icon = notification.type === 'new_startup' ? 'fa-rocket' : 
                    notification.type === 'new_user' ? 'fa-user-plus' : 'fa-bell';
        
        html += `
            <div class="notification-item ${notification.read ? 'read' : 'unread'}">
                <div class="notification-icon">
                    <i class="fas ${icon}"></i>
                </div>
                <div class="notification-content">
                    <div class="notification-title">${notification.title}</div>
                    <div class="notification-time">${formatDate(notification.timestamp)}</div>
                </div>
            </div>
        `;
    });
    
    if (notifications.length > 5) {
        html += `<div class="notification-more">+${notifications.length - 5} ta yana</div>`;
    }
    
    dropdown.innerHTML = html;
    dropdown.style.display = 'block';
    
    // Tashqariga bosilsa yopish
    setTimeout(() => {
        document.addEventListener('click', function closeDropdown(e) {
            if (!dropdown.contains(e.target) && e.target.id !== 'notificationBtn') {
                dropdown.style.display = 'none';
                document.removeEventListener('click', closeDropdown);
            }
        });
    }, 100);
}

function startNotificationChecker() {
    if (notificationsInterval) {
        clearInterval(notificationsInterval);
    }
    
    notificationsInterval = setInterval(async () => {
        if (currentUser) {
            await checkNewNotifications();
        }
    }, 60000); // Har 1 daqiqa
    
    // Dastlabki tekshirish
    if (currentUser) {
        checkNewNotifications();
    }
}

function stopNotificationChecker() {
    if (notificationsInterval) {
        clearInterval(notificationsInterval);
        notificationsInterval = null;
    }
}

async function checkNewNotifications() {
    try {
        const response = await fetch('/api/notifications');
        const data = await response.json();
        
        if (data.success) {
            const unreadCount = data.data.filter(n => !n.read).length;
            const notificationCount = document.getElementById('notificationCount');
            
            if (notificationCount) {
                if (unreadCount > 0) {
                    notificationCount.textContent = unreadCount > 99 ? '99+' : unreadCount;
                    notificationCount.style.display = 'block';
                } else {
                    notificationCount.style.display = 'none';
                }
            }
        }
    } catch (error) {
        console.error('Notification tekshirish xatosi:', error);
    }
}

function toggleLegend() {
    const legend = document.getElementById('distributionLegend');
    if (legend) {
        legend.style.display = legend.style.display === 'none' ? 'block' : 'none';
    }
}

async function exportUsers() {
    try {
        showLoading();
        const users = await fetchAllUsers();
        hideLoading();
        
        if (!users.length) {
            showToast('Eksport qilish uchun foydalanuvchi yo\'q', 'info');
            return;
        }
        
        const columns = [
            { key: 'user_id', label: 'ID' },
            { key: 'first_name', label: 'Ism' },
            { key: 'last_name', label: 'Familiya' },
            { key: 'username', label: 'Username' },
            { key: 'phone', label: 'Telefon' },
            { key: 'specialization', label: 'Mutaxassislik' },
            { key: 'experience', label: 'Tajriba' },
            { key: 'startup_count', label: 'Startaplar soni' },
            { key: 'status', label: 'Status' },
            { key: 'joined_at', label: 'Ro\'yxat sanasi' }
        ];
        
        const csv = toCSV(users, columns);
        downloadCSV(csv, `users_export_${new Date().toISOString().slice(0, 10)}.csv`);
        showToast('Foydalanuvchilar CSV yuklab olindi', 'success');
    } catch (error) {
        hideLoading();
        console.error('Export users error:', error);
        showToast('Eksport qilishda xatolik', 'error');
    }
}

async function exportStartups() {
    try {
        showLoading();
        const startups = await fetchAllStartups();
        hideLoading();
        
        if (!startups.length) {
            showToast('Eksport qilish uchun startap yo\'q', 'info');
            return;
        }
        
        const columns = [
            { key: 'id', label: 'ID' },
            { key: 'name', label: 'Nomi' },
            { key: 'owner_name', label: 'Egasi' },
            { key: 'category', label: 'Kategoriya' },
            { key: 'status', label: 'Status' },
            { key: 'member_count', label: 'A\'zolar soni' },
            { key: 'max_members', label: 'Maks a\'zolar' },
            { key: 'created_at', label: 'Yaratilgan sana' },
            { key: 'description', label: 'Tavsif' }
        ];
        
        const csv = toCSV(startups, columns);
        downloadCSV(csv, `startups_export_${new Date().toISOString().slice(0, 10)}.csv`);
        showToast('Startaplar CSV yuklab olindi', 'success');
    } catch (error) {
        hideLoading();
        console.error('Export startups error:', error);
        showToast('Eksport qilishda xatolik', 'error');
    }
}

async function fetchAllUsers() {
    let page = 1;
    let totalPages = 1;
    const perPage = 200;
    const all = [];
    
    do {
        const response = await fetch(`/api/users?page=${page}&per_page=${perPage}`);
        const data = await response.json();
        if (!data.success) {
            throw new Error(data.error || 'Foydalanuvchilarni olishda xatolik');
        }
        all.push(...(data.data || []));
        totalPages = data.pagination?.total_pages || 1;
        page += 1;
    } while (page <= totalPages);
    
    return all;
}

async function fetchAllStartups() {
    let page = 1;
    let totalPages = 1;
    const perPage = 200;
    const all = [];
    
    do {
        const response = await fetch(`/api/startups?page=${page}&per_page=${perPage}&status=all&category=all`);
        const data = await response.json();
        if (!data.success) {
            throw new Error(data.error || 'Startaplarni olishda xatolik');
        }
        all.push(...(data.data || []));
        totalPages = data.pagination?.total_pages || 1;
        page += 1;
    } while (page <= totalPages);
    
    return all;
}

function toCSV(rows, columns) {
    const header = columns.map(col => csvEscape(col.label)).join(',');
    const lines = rows.map(row => {
        return columns.map(col => csvEscape(row[col.key])).join(',');
    });
    return [header, ...lines].join('\n');
}

function csvEscape(value) {
    if (value === null || value === undefined) return '""';
    const str = String(value).replace(/"/g, '""');
    return `"${str}"`;
}

function downloadCSV(csv, filename) {
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.click();
    URL.revokeObjectURL(link.href);
}

function exportChart(chartType) {
    const canvas = document.getElementById(chartType + 'Chart');
    if (canvas) {
        const link = document.createElement('a');
        link.download = chartType + '-chart.png';
        link.href = canvas.toDataURL('image/png');
        link.click();
        showToast('Grafik yuklab olindi', 'success');
    }
}

function handleKeyboardShortcuts(e) {
    // Ctrl + K qidirish
    if (e.ctrlKey && e.key === 'k') {
        e.preventDefault();
        const searchInput = document.getElementById('searchInput');
        if (searchInput) {
            searchInput.focus();
        }
    }
    
    // ESC modal yopish
    if (e.key === 'Escape') {
        closeModal();
        
        // Notification dropdown yopish
        const dropdown = document.getElementById('notificationDropdown');
        if (dropdown && dropdown.style.display === 'block') {
            dropdown.style.display = 'none';
        }
    }
    
    // F5 - refresh current page
    if (e.key === 'F5') {
        e.preventDefault();
        switch(currentPage) {
            case 'dashboard':
                loadDashboard();
                break;
            case 'users':
                loadUsers();
                break;
            case 'startups':
                loadStartups();
                break;
            case 'statistics':
                loadDetailedStatistics();
                break;
            case 'system':
                loadSystemHealth();
                break;
        }
        showToast('Sahifa yangilandi', 'info');
    }
}

// ==================== ADDITIONAL FUNCTIONS ====================

// Admins page functions
async function loadAdmins() {
    try {
        const response = await fetch('/api/admins');
        const data = await response.json();
        
        if (data.success) {
            updateAdminsTable(data.data || []);
        } else {
            showToast(data.error || 'Adminlarni yuklashda xatolik', 'error');
        }
    } catch (error) {
        console.error('Adminlar yuklash xatosi:', error);
        showToast('Adminlarni yuklashda xatolik', 'error');
    }
}

function updateAdminsTable(admins) {
    const tbody = document.getElementById('adminsTableBody');
    if (!tbody) return;
    
    let html = '';
    admins.forEach(admin => {
        const isCurrentUser = admin.username === currentUser?.username;
        const roleClass = admin.role === 'superadmin' ? 'superadmin' : 'admin';
        
        html += `
            <tr>
                <td>${admin.id}</td>
                <td><strong>${admin.username}</strong> ${isCurrentUser ? '<span class="current-user-badge">(Siz)</span>' : ''}</td>
                <td>${admin.full_name}</td>
                <td>${admin.email}</td>
                <td><span class="status-badge ${roleClass}">${admin.role}</span></td>
                <td>${formatDate(admin.last_login)}</td>
                <td>
                    <div class="table-actions">
                        ${!isCurrentUser ? `
                            <button class="action-btn delete-btn" onclick="deleteAdmin(${admin.id})" title="O'chirish">
                                <i class="fas fa-trash"></i>
                            </button>
                        ` : '<span class="current-user-label">Siz</span>'}
                    </div>
                </td>
            </tr>
        `;
    });
    
    tbody.innerHTML = html;
}

async function handleAddAdmin(e) {
    e.preventDefault();
    
    const formData = {
        username: document.getElementById('newAdminUsername').value,
        password: document.getElementById('newAdminPassword').value,
        full_name: document.getElementById('newAdminFullName').value,
        email: document.getElementById('newAdminEmail').value,
        role: document.getElementById('newAdminRole').value
    };
    
    // Validatsiya
    if (!formData.username || !formData.password || !formData.full_name || !formData.email) {
        showToast('Barcha maydonlarni to\'ldiring', 'error');
        return;
    }
    
    if (formData.password.length < 6) {
        showToast('Parol kamida 6 belgidan iborat bo\'lishi kerak', 'error');
        return;
    }
    
    try {
        showLoading();
        const response = await fetch('/api/admins', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });
        const data = await response.json();
        hideLoading();
        
        if (data.success) {
            showToast('Yangi admin qo\'shildi', 'success');
            closeModal();
            document.getElementById('addAdminForm').reset();
            loadAdmins();
        } else {
            showToast(data.error || 'Admin qo\'shishda xatolik', 'error');
        }
    } catch (error) {
        hideLoading();
        console.error('Admin qo\'shish xatosi:', error);
        showToast('Admin qo\'shishda xatolik', 'error');
    }
}

function deleteAdmin(adminId) {
    if (!confirm('Adminni o\'chirishni tasdiqlaysizmi?')) {
        return;
    }
    
    (async () => {
        try {
            showLoading();
            const response = await fetch(`/api/admins/${adminId}`, { method: 'DELETE' });
            const data = await response.json();
            hideLoading();
            
            if (data.success) {
                showToast('Admin o\'chirildi', 'success');
                loadAdmins();
            } else {
                showToast(data.error || 'Admin o\'chirishda xatolik', 'error');
            }
        } catch (error) {
            hideLoading();
            console.error('Admin o\'chirish xatosi:', error);
            showToast('Admin o\'chirishda xatolik', 'error');
        }
    })();
}

// ==================== GLOBAL FUNCTIONS ====================

window.showPage = showPage;
window.filterActivity = filterActivity;
window.toggleLegend = toggleLegend;
window.exportChart = exportChart;
window.exportUsers = exportUsers;
window.exportStartups = exportStartups;
window.viewUser = viewUser;
window.viewStartup = viewStartup;
window.approveStartup = approveStartup;
window.rejectStartup = rejectStartup;
window.completeStartup = completeStartup;
window.openBroadcastModal = openBroadcastModal;
window.clearMessageForm = clearMessageForm;
window.openAddAdminModal = openAddAdminModal;
window.deleteAdmin = deleteAdmin;
window.saveNotificationSettings = saveNotificationSettings;
window.closeModal = closeModal;
window.showNotifications = showNotifications;

// Initialize the app
window.onload = initializeApp;
