document.addEventListener('DOMContentLoaded', function() {
    // Menu item buttons
    setupMenuButtons();
    
    // Notification button
    setupNotificationButton();
    
    // Course cards
    setupCourseCards();
    
    // Calendar functionality
    setupCalendar();
    
    // To-do list functionality
    setupTodoList();
    
    // AI Assistant button
    setupAIAssistant();
    
    // Add API key check
    checkApiKeyStatus();
});

function setupMenuButtons() {
    const menuItems = {
        'dashboard': '/',
        'courses': '/courses',
        'calendar': '/calendar',
        'messages': '/messages',
        'assignments': '/assignments',
        'graphing-calculator': '/graphing-calculator',
        'video-recommender': '/recommend-videos',
        'grades': '/check-grades',
        'todo-list': '/todo-list',
        'ai-assistant': '/ai-assistant'
    };

    Object.entries(menuItems).forEach(([id, route]) => {
        const element = document.getElementById(id);
        if (element) {
            element.addEventListener('click', () => {
                window.location.href = route;
            });
        }
    });
}

function setupNotificationButton() {
    const notificationBtn = document.querySelector('.notification-btn');
    if (notificationBtn) {
        notificationBtn.addEventListener('click', async () => {
            try {
                const response = await fetch('/api/notifications');
                const notifications = await response.json();
                displayNotifications(notifications);
            } catch (error) {
                console.error('Error fetching notifications:', error);
            }
        });
    }
}

function setupCourseCards() {
    const courseCards = document.querySelectorAll('.course-card');
    courseCards.forEach(card => {
        card.addEventListener('click', () => {
            const courseId = card.dataset.courseId;
            if (courseId) {
                window.location.href = `/course/${courseId}`;
            }
        });
    });
}

function setupCalendar() {
    const calendarDays = document.querySelectorAll('.calendar-day');
    calendarDays.forEach(day => {
        day.addEventListener('click', () => {
            const date = day.dataset.date;
            if (date) {
                showDayEvents(date);
            }
        });
    });
}

function setupTodoList() {
    const addTaskInput = document.getElementById('add-task-input');
    const addTaskBtn = document.getElementById('add-task-btn');

    if (addTaskInput && addTaskBtn) {
        addTaskBtn.addEventListener('click', async () => {
            const taskText = addTaskInput.value.trim();
            if (taskText) {
                await addNewTask(taskText);
                addTaskInput.value = '';
                refreshTodoList();
            }
        });

        // Handle enter key
        addTaskInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                addTaskBtn.click();
            }
        });
    }

    // Setup task completion toggles
    setupTaskToggles();
}

function setupAIAssistant() {
    const aiAssistantBtn = document.getElementById('ai-assistant-btn');
    if (aiAssistantBtn) {
        aiAssistantBtn.addEventListener('click', () => {
            toggleAIAssistant();
        });
    }
}

// Helper functions
async function addNewTask(taskText) {
    try {
        const response = await fetch('/api/todo', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ task: taskText })
        });
        return await response.json();
    } catch (error) {
        console.error('Error adding task:', error);
    }
}

async function refreshTodoList() {
    try {
        const response = await fetch('/api/todo');
        const tasks = await response.json();
        updateTodoListUI(tasks);
    } catch (error) {
        console.error('Error refreshing todo list:', error);
    }
}

function updateTodoListUI(tasks) {
    const todoList = document.querySelector('.todo-list');
    if (todoList) {
        todoList.innerHTML = tasks.map(task => `
            <div class="todo-item" data-id="${task.id}">
                <input type="checkbox" ${task.completed ? 'checked' : ''}>
                <span class="${task.completed ? 'completed' : ''}">${task.text}</span>
                <button class="delete-task">×</button>
            </div>
        `).join('');
        setupTaskToggles();
    }
}

function setupTaskToggles() {
    document.querySelectorAll('.todo-item input[type="checkbox"]').forEach(checkbox => {
        checkbox.addEventListener('change', async (e) => {
            const taskId = e.target.closest('.todo-item').dataset.id;
            await toggleTaskCompletion(taskId);
        });
    });

    document.querySelectorAll('.delete-task').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            const taskId = e.target.closest('.todo-item').dataset.id;
            await deleteTask(taskId);
            refreshTodoList();
        });
    });
}

async function toggleTaskCompletion(taskId) {
    try {
        await fetch(`/api/todo/${taskId}/toggle`, { method: 'POST' });
    } catch (error) {
        console.error('Error toggling task:', error);
    }
}

async function deleteTask(taskId) {
    try {
        await fetch(`/api/todo/${taskId}`, { method: 'DELETE' });
    } catch (error) {
        console.error('Error deleting task:', error);
    }
}

function toggleAIAssistant() {
    const aiSidebar = document.querySelector('.ai-sidebar');
    if (aiSidebar) {
        aiSidebar.classList.toggle('open');
    }
}

function displayNotifications(notifications) {
    // Implementation for displaying notifications
    // You can create a modal or dropdown here
    console.log('Notifications:', notifications);
}

function showDayEvents(date) {
    // Implementation for showing events for a specific day
    console.log('Showing events for:', date);
}

// Add this function to check API key status
function checkApiKeyStatus() {
    console.log("Checking API key status...");
    fetch('/api/check-canvas-api-key')
        .then(response => {
            console.log("API key check response status:", response.status);
            return response.json();
        })
        .then(data => {
            console.log("API key check data:", data);
            if (!data.has_api_key) {
                // Show a notification or modal to prompt user to add API key
                const notification = document.createElement('div');
                notification.className = 'api-key-notification';
                notification.innerHTML = `
                    <p>Canvas API key not found. Please update your profile settings.</p>
                    <button id="go-to-profile">Update Profile</button>
                `;
                document.body.appendChild(notification);
                
                document.getElementById('go-to-profile').addEventListener('click', () => {
                    window.location.href = '/profile';
                });
            }
        })
        .catch(error => {
            console.error('Error checking API key status:', error);
        });
}