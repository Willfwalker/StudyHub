function navigateToDashboard() {
    // Check if this is a cold start
    const isColdStart = !sessionStorage.getItem('dashboardLoaded');
    
    if (isColdStart) {
        // Navigate to dashboard with cold start parameter
        window.location.href = '/dashboard?cold_start=true';
    } else {
        // Normal navigation
        window.location.href = '/dashboard';
    }
}

// Add event listener to set the flag when dashboard loads
document.addEventListener('DOMContentLoaded', function() {
    // Only set the flag if we're on the dashboard page
    if (window.location.pathname === '/dashboard') {
        sessionStorage.setItem('dashboardLoaded', 'true');
    }
}); 