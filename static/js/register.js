function registerUser(event) {
    event.preventDefault();
    
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    const canvasApiKey = document.getElementById('canvasApiKey').value;
    const canvasUrl = document.getElementById('canvasUrl').value;
    const googleFolderId = document.getElementById('googleFolderId')?.value || '';
    
    // Validate required fields
    const missingFields = [];
    if (!email) missingFields.push('Email');
    if (!password) missingFields.push('Password');
    if (!canvasApiKey) missingFields.push('Canvas API Key');
    if (!canvasUrl) missingFields.push('Canvas URL');
    
    // Check if any required fields are missing
    if (missingFields.length > 0) {
        // Display error message
        const errorElement = document.getElementById('errorMessage') || document.createElement('div');
        errorElement.textContent = `Missing required fields: ${missingFields.join(', ')}`;
        errorElement.style.color = 'red';
        errorElement.style.marginTop = '10px';
        
        if (!document.getElementById('errorMessage')) {
            const submitButton = event.target.querySelector('button[type="submit"]');
            submitButton.parentNode.appendChild(errorElement);
            errorElement.id = 'errorMessage';
        }
        return; // Stop execution if fields are missing
    }
    
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
                    password: password,
                    uid: userCredential.user.uid,
                    canvas_api_key: canvasApiKey,
                    canvas_url: canvasUrl,
                    google_folder_id: googleFolderId
                })
            });
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log("Registration successful, data:", data);
                
                // Check if we need to redirect for Google auth
                if (data.redirect_url && data.redirect_url !== 'undefined') {
                    console.log("Redirecting to:", data.redirect_url);
                    window.location.href = data.redirect_url;
                } else {
                    console.log("Fallback: Redirecting to dashboard");
                    window.location.href = '/dashboard';
                }
            } else {
                throw new Error(data.error || 'Registration failed');
            }
        })
        .catch((error) => {
            console.error('Error:', error);
            // Display error in a more user-friendly way
            const errorElement = document.getElementById('errorMessage') || document.createElement('div');
            errorElement.textContent = error.message;
            errorElement.style.color = 'red';
            errorElement.style.marginTop = '10px';
            
            if (!document.getElementById('errorMessage')) {
                submitButton.parentNode.appendChild(errorElement);
                errorElement.id = 'errorMessage';
            }
            
            // Reset button state on error
            submitButton.textContent = originalText;
            submitButton.disabled = false;
        });
} 