function registerUser(event) {
    event.preventDefault();
    
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    const canvasApiKey = document.getElementById('canvasApiKey').value;
    const canvasUrl = document.getElementById('canvasUrl').value;
    
    // Get the submit button and change its text
    const submitButton = event.target.querySelector('button[type="submit"]');
    const originalText = submitButton.textContent;
    submitButton.textContent = 'Creating Account...';
    submitButton.disabled = true;  // Disable the button while processing
    
    // Create user with Firebase
    firebase.auth().createUserWithEmailAndPassword(email, password)
        .then((userCredential) => {
            // Register with our backend
            return fetch('/api/register', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    email: email,
                    uid: userCredential.user.uid,
                    canvas_api_key: canvasApiKey,
                    canvas_url: canvasUrl
                })
            });
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                window.location.href = data.redirect;
            } else {
                throw new Error(data.error || 'Registration failed');
            }
        })
        .catch((error) => {
            console.error('Error:', error);
            alert(error.message);
            // Reset button state on error
            submitButton.textContent = originalText;
            submitButton.disabled = false;
        });
} 