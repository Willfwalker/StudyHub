function createNotes(courseId) {
    fetch(`/create-notes/${courseId}`)
        .then(response => response.json())
        .then(data => {
            if (data.needs_auth) {
                // Open Google auth in popup
                const authWindow = window.open(
                    data.auth_url,
                    'Google Authorization',
                    'width=600,height=600'
                );

                // Listen for auth completion
                window.addEventListener('message', function(event) {
                    if (event.data === 'google-auth-success') {
                        authWindow.close();
                        // Retry creating notes
                        createNotes(courseId);
                    }
                }, false);
            } else if (data.url) {
                // Open the created document in a new tab
                window.open(data.url, '_blank');
            } else {
                alert('Error creating notes: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Error creating notes. Please try again.');
        });
}
