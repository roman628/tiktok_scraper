function isTikTokVideoURL(url) {
  const tiktokVideoPattern = /^https:\/\/www\.tiktok\.com\/@[^\/]+\/video\/\d+/;
  return tiktokVideoPattern.test(url);
}

// Extract MS_TOKEN from TikTok cookies
function extractMSToken() {
  // Try to get msToken from cookies
  const cookies = document.cookie.split('; ');
  for (const cookie of cookies) {
    const [name, value] = cookie.split('=');
    if (name === 'msToken') {
      return value;
    }
  }
  
  // Try to get from localStorage or sessionStorage as backup
  try {
    const localStorageToken = localStorage.getItem('msToken');
    if (localStorageToken) return localStorageToken;
    
    const sessionStorageToken = sessionStorage.getItem('msToken');
    if (sessionStorageToken) return sessionStorageToken;
  } catch (e) {
    // Storage access might be restricted
  }
  
  return null;
}

// Persistent notification system with counter
let notificationElement = null;
let urlCounter = 0;
let closeTimeout = null;

function createOrUpdateNotification() {
  // Clear any existing close timeout
  if (closeTimeout) {
    clearTimeout(closeTimeout);
    closeTimeout = null;
  }
  
  // Create notification if it doesn't exist
  if (!notificationElement) {
    notificationElement = document.createElement('div');
    notificationElement.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      padding: 12px 20px;
      background: #2ed573;
      color: white;
      border-radius: 6px;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      font-size: 14px;
      z-index: 10000;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
      transition: all 0.3s ease;
      transform: translateX(100%);
    `;
    document.body.appendChild(notificationElement);
    
    // Slide in
    setTimeout(() => {
      notificationElement.style.transform = 'translateX(0)';
    }, 100);
  }
  
  // Update counter text
  notificationElement.textContent = `✓ ${urlCounter} TikTok URL${urlCounter !== 1 ? 's' : ''} added`;
  
  // Add pulse animation for counter update
  notificationElement.style.animation = 'pulse 0.3s ease';
  setTimeout(() => {
    notificationElement.style.animation = '';
  }, 300);
  
  // Set timeout to close after 3 seconds of inactivity
  closeTimeout = setTimeout(() => {
    if (notificationElement) {
      notificationElement.style.transform = 'translateX(100%)';
      setTimeout(() => {
        if (notificationElement && notificationElement.parentNode) {
          notificationElement.parentNode.removeChild(notificationElement);
        }
        notificationElement = null;
        urlCounter = 0;
      }, 300);
    }
  }, 3000);
}

function showNotification(message, isError = false) {
  if (isError) {
    // For errors, create a separate temporary notification
    const errorNotification = document.createElement('div');
    errorNotification.style.cssText = `
      position: fixed;
      top: ${notificationElement ? '80px' : '20px'};
      right: 20px;
      padding: 12px 20px;
      background: #ff4757;
      color: white;
      border-radius: 6px;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      font-size: 14px;
      z-index: 10000;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
      transition: all 0.3s ease;
      transform: translateX(100%);
    `;
    errorNotification.textContent = message;
    document.body.appendChild(errorNotification);
    
    setTimeout(() => {
      errorNotification.style.transform = 'translateX(0)';
    }, 100);
    
    setTimeout(() => {
      errorNotification.style.transform = 'translateX(100%)';
      setTimeout(() => {
        if (errorNotification.parentNode) {
          errorNotification.parentNode.removeChild(errorNotification);
        }
      }, 300);
    }, 3000);
  } else if (message.includes('TikTok URL added')) {
    // Increment counter and update persistent notification
    urlCounter++;
    createOrUpdateNotification();
  } else {
    // For other success messages (like MS_TOKEN), show temporary notification
    const tempNotification = document.createElement('div');
    tempNotification.style.cssText = `
      position: fixed;
      top: ${notificationElement ? '80px' : '20px'};
      right: 20px;
      padding: 12px 20px;
      background: #2ed573;
      color: white;
      border-radius: 6px;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      font-size: 14px;
      z-index: 10000;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
      transition: all 0.3s ease;
      transform: translateX(100%);
    `;
    tempNotification.textContent = message;
    document.body.appendChild(tempNotification);
    
    setTimeout(() => {
      tempNotification.style.transform = 'translateX(0)';
    }, 100);
    
    setTimeout(() => {
      tempNotification.style.transform = 'translateX(100%)';
      setTimeout(() => {
        if (tempNotification.parentNode) {
          tempNotification.parentNode.removeChild(tempNotification);
        }
      }, 300);
    }, 3000);
  }
}

// Add CSS animation for pulse effect
if (!document.getElementById('tiktok-extension-styles')) {
  const style = document.createElement('style');
  style.id = 'tiktok-extension-styles';
  style.textContent = `
    @keyframes pulse {
      0% { transform: translateX(0) scale(1); }
      50% { transform: translateX(0) scale(1.05); }
      100% { transform: translateX(0) scale(1); }
    }
  `;
  document.head.appendChild(style);
}

let processedURLs = new Set();
let isProcessing = false;
let cachedMSToken = null; // Cache MS_TOKEN for the session

function checkAndCaptureURL() {
  const currentURL = window.location.href;
  
  if (isTikTokVideoURL(currentURL) && !processedURLs.has(currentURL) && !isProcessing) {
    isProcessing = true;
    processedURLs.add(currentURL);
    
    // Don't send MS_TOKEN with every URL, it's already cached on page load
    browser.runtime.sendMessage({
      type: 'TIKTOK_URL_FOUND',
      url: currentURL
    });
  }
}

// Send MS_TOKEN on page load/refresh only
function sendMSToken() {
  const msToken = extractMSToken();
  if (msToken && msToken !== cachedMSToken) {
    cachedMSToken = msToken; // Cache it for this session
    console.log('MS_TOKEN found:', msToken.substring(0, 20) + '...');
    browser.runtime.sendMessage({
      type: 'MS_TOKEN_FOUND',
      msToken: msToken
    }).catch(err => {
      console.error('Error sending MS_TOKEN:', err);
    });
  }
}

browser.runtime.onMessage.addListener((message, sender, sendResponse) => {
  switch (message.type) {
    case 'CHECK_TIKTOK_URL':
      checkAndCaptureURL();
      break;
    case 'URL_ADDED_SUCCESS':
      isProcessing = false;
      showNotification(`✓ TikTok URL added`);
      break;
    case 'URL_ADDED_ERROR':
      isProcessing = false;
      processedURLs.delete(message.url);
      showNotification(`✗ Error adding URL: ${message.error}`, true);
      break;
    case 'MS_TOKEN_UPDATE_SUCCESS':
      showNotification(`✓ MS_TOKEN updated in config`);
      break;
    case 'MS_TOKEN_UPDATE_ERROR':
      showNotification(`✗ Error updating MS_TOKEN: ${message.error}`, true);
      break;
    case 'GET_MS_TOKEN':
      // Return MS_TOKEN to popup
      const msToken = extractMSToken();
      sendResponse({ msToken: msToken });
      return true; // Indicates we will send a response asynchronously
  }
});

let lastURL = window.location.href;
const observer = new MutationObserver(() => {
  if (window.location.href !== lastURL) {
    lastURL = window.location.href;
    setTimeout(() => {
      checkAndCaptureURL();
      // Don't resend MS_TOKEN on navigation, only on refresh
    }, 100);
  }
});

observer.observe(document.body, {
  childList: true,
  subtree: true
});

checkAndCaptureURL();

// Send MS_TOKEN only on initial page load
if (window.location.hostname.includes('tiktok.com')) {
  console.log('TikTok page detected, will send MS_TOKEN on initial load...');
  // Wait a bit for cookies to be available
  setTimeout(() => {
    console.log('Attempting to send MS_TOKEN...');
    sendMSToken();
  }, 2000);
  
  // No longer send MS_TOKEN periodically - only on page refresh
}