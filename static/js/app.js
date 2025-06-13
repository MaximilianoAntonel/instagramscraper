/**
 * Instagram Post Scraper - Client-side JavaScript
 * Handles form validation, submission, and UI interactions
 */

// DOM elements
const scrapeForm = document.getElementById('scrapeForm');
const usernamesInput = document.getElementById('usernames');
const numPostsSelect = document.getElementById('num_posts');
const scrapeBtn = document.getElementById('scrapeBtn');
const clearBtn = document.getElementById('clearBtn');
const loadingState = document.getElementById('loadingState');
const successMessage = document.getElementById('successMessage');
const errorMessage = document.getElementById('errorMessage');
const successText = document.getElementById('successText');
const errorText = document.getElementById('errorText');
const sheetsLink = document.getElementById('sheetsLink');

// State management
let isSubmitting = false;

/**
 * Initialize the application
 */
document.addEventListener('DOMContentLoaded', function() {
    initializeEventListeners();
    initializeFormValidation();
    
    // Focus on the usernames input for better UX
    if (usernamesInput) {
        usernamesInput.focus();
    }
    
    console.log('Instagram Post Scraper initialized');
});

/**
 * Set up event listeners
 */
function initializeEventListeners() {
    // Form submission
    if (scrapeForm) {
        scrapeForm.addEventListener('submit', handleFormSubmission);
    }
    
    // Clear button
    if (clearBtn) {
        clearBtn.addEventListener('click', clearFormData);
    }
    
    // Real-time validation
    if (usernamesInput) {
        usernamesInput.addEventListener('input', validateUsernames);
        usernamesInput.addEventListener('blur', validateUsernames);
    }
    
    // Prevent multiple submissions
    if (scrapeBtn) {
        scrapeBtn.addEventListener('click', function(e) {
            if (isSubmitting) {
                e.preventDefault();
                return false;
            }
        });
    }
}

/**
 * Initialize form validation
 */
function initializeFormValidation() {
    // Add Bootstrap validation classes
    const forms = document.querySelectorAll('.needs-validation');
    
    Array.prototype.slice.call(forms).forEach(function(form) {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        }, false);
    });
}

/**
 * Handle form submission
 */
async function handleFormSubmission(event) {
    event.preventDefault();
    
    if (isSubmitting) {
        return false;
    }
    
    // Validate form before submission
    if (!validateForm()) {
        return false;
    }
    
    isSubmitting = true;
    showLoadingState();
    
    try {
        const formData = new FormData(scrapeForm);
        
        // Add timestamp for tracking
        formData.append('timestamp', new Date().toISOString());
        
        const response = await fetch('/scrape', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.success) {
            showSuccessMessage(result.message, result.sheets_url);
        } else {
            showErrorMessage(result.message);
        }
        
    } catch (error) {
        console.error('Submission error:', error);
        showErrorMessage('Network error occurred. Please check your connection and try again.');
    } finally {
        isSubmitting = false;
        hideLoadingState();
    }
}

/**
 * Validate the entire form
 */
function validateForm() {
    let isValid = true;
    
    // Validate usernames
    if (!validateUsernames()) {
        isValid = false;
    }
    
    // Validate number of posts
    const numPosts = parseInt(numPostsSelect.value);
    if (!numPosts || numPosts < 1 || numPosts > 5) {
        showFieldError('num_posts', 'Please select a valid number of posts (1-5)');
        isValid = false;
    }
    
    return isValid;
}

/**
 * Validate Instagram usernames
 */
function validateUsernames() {
    const usernamesText = usernamesInput.value.trim();
    const errorElement = document.getElementById('usernames-error');
    
    // Clear previous validation state
    usernamesInput.classList.remove('is-invalid', 'is-valid');
    
    if (!usernamesText) {
        showFieldError('usernames', 'Please enter at least one Instagram username');
        return false;
    }
    
    // Parse usernames
    const usernames = parseUsernames(usernamesText);
    
    if (usernames.length === 0) {
        showFieldError('usernames', 'Please enter valid Instagram usernames');
        return false;
    }
    
    if (usernames.length > 10) {
        showFieldError('usernames', `Too many usernames (${usernames.length}/10). Maximum 10 allowed.`);
        return false;
    }
    
    // Validate username format
    const invalidUsernames = usernames.filter(username => !isValidUsername(username));
    if (invalidUsernames.length > 0) {
        showFieldError('usernames', `Invalid usernames detected: ${invalidUsernames.join(', ')}`);
        return false;
    }
    
    // Show success state
    usernamesInput.classList.add('is-valid');
    if (errorElement) {
        errorElement.textContent = `${usernames.length} username(s) ready for scraping`;
        errorElement.className = 'valid-feedback';
    }
    
    return true;
}

/**
 * Parse usernames from input text
 */
function parseUsernames(text) {
    const usernames = [];
    
    // Split by comma, newline, or semicolon
    const parts = text.split(/[,;\n]+/);
    
    for (let part of parts) {
        const username = part.trim().replace(/^@/, ''); // Remove @ if present
        if (username) {
            usernames.push(username);
        }
    }
    
    return usernames;
}

/**
 * Validate individual username format
 */
function isValidUsername(username) {
    // Instagram username rules: 1-30 characters, letters, numbers, dots, underscores
    const usernameRegex = /^[a-zA-Z0-9_.]{1,30}$/;
    return usernameRegex.test(username);
}

/**
 * Show field-specific error
 */
function showFieldError(fieldId, message) {
    const field = document.getElementById(fieldId);
    const errorElement = document.getElementById(`${fieldId}-error`);
    
    if (field) {
        field.classList.add('is-invalid');
        field.classList.remove('is-valid');
    }
    
    if (errorElement) {
        errorElement.textContent = message;
        errorElement.className = 'invalid-feedback';
    }
}

/**
 * Clear all form data
 */
function clearFormData() {
    if (scrapeForm) {
        scrapeForm.reset();
        
        // Clear validation states
        const inputs = scrapeForm.querySelectorAll('.form-control, .form-select');
        inputs.forEach(input => {
            input.classList.remove('is-invalid', 'is-valid');
        });
        
        // Clear error messages
        const errorElements = scrapeForm.querySelectorAll('.invalid-feedback, .valid-feedback');
        errorElements.forEach(element => {
            element.textContent = '';
        });
        
        // Hide result messages
        hideAllMessages();
        
        // Focus back on usernames input
        if (usernamesInput) {
            usernamesInput.focus();
        }
    }
}

/**
 * Show loading state
 */
function showLoadingState() {
    hideAllMessages();
    
    if (loadingState) {
        loadingState.classList.remove('d-none');
        loadingState.classList.add('fade-in');
    }
    
    // Disable form elements
    setFormEnabled(false);
}

/**
 * Hide loading state
 */
function hideLoadingState() {
    if (loadingState) {
        loadingState.classList.add('d-none');
    }
    
    // Re-enable form elements
    setFormEnabled(true);
}

/**
 * Show success message
 */
function showSuccessMessage(message, sheetsUrl) {
    hideAllMessages();
    
    if (successMessage && successText) {
        successText.textContent = message;
        
        if (sheetsUrl && sheetsLink) {
            sheetsLink.href = sheetsUrl;
        }
        
        successMessage.classList.remove('d-none');
        successMessage.classList.add('fade-in');
        
        // Scroll to success message
        successMessage.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
}

/**
 * Show error message
 */
function showErrorMessage(message) {
    hideAllMessages();
    
    if (errorMessage && errorText) {
        errorText.textContent = message;
        errorMessage.classList.remove('d-none');
        errorMessage.classList.add('fade-in');
        
        // Scroll to error message
        errorMessage.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
}

/**
 * Hide all result messages
 */
function hideAllMessages() {
    const messages = [loadingState, successMessage, errorMessage];
    messages.forEach(element => {
        if (element) {
            element.classList.add('d-none');
            element.classList.remove('fade-in');
        }
    });
}

/**
 * Enable or disable form elements
 */
function setFormEnabled(enabled) {
    const elements = scrapeForm.querySelectorAll('input, select, button, textarea');
    elements.forEach(element => {
        element.disabled = !enabled;
    });
    
    // Update button text and icon
    if (scrapeBtn) {
        const icon = scrapeBtn.querySelector('i');
        const text = scrapeBtn.querySelector('span:not(.visually-hidden)') || scrapeBtn;
        
        if (enabled) {
            if (icon) icon.className = 'fas fa-play me-2';
            scrapeBtn.innerHTML = '<i class="fas fa-play me-2"></i>Start Scraping';
        } else {
            if (icon) icon.className = 'fas fa-spinner fa-spin me-2';
            scrapeBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Processing...';
        }
    }
}

/**
 * Utility function to show toast notifications (if needed)
 */
function showToast(message, type = 'info') {
    // Create a simple toast notification
    const toast = document.createElement('div');
    toast.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    toast.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    toast.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(toast);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (toast.parentNode) {
            toast.parentNode.removeChild(toast);
        }
    }, 5000);
}

// Export functions for potential external use
window.InstagramScraper = {
    validateUsernames,
    clearFormData,
    showToast
};
