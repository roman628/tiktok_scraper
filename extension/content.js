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

function showNotification(message, isError = false) {
  const notification = document.createElement('div');
  notification.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    padding: 12px 20px;
    background: ${isError ? '#ff4757' : '#2ed573'};
    color: white;
    border-radius: 6px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-size: 14px;
    z-index: 10000;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    transition: all 0.3s ease;
    transform: translateX(100%);
  `;
  notification.textContent = message;
  
  document.body.appendChild(notification);
  
  setTimeout(() => {
    notification.style.transform = 'translateX(0)';
  }, 100);
  
  setTimeout(() => {
    notification.style.transform = 'translateX(100%)';
    setTimeout(() => {
      if (notification.parentNode) {
        notification.parentNode.removeChild(notification);
      }
    }, 300);
  }, 3000);
}

let processedURLs = new Set();
let isProcessing = false;

function checkAndCaptureURL() {
  const currentURL = window.location.href;
  
  if (isTikTokVideoURL(currentURL) && !processedURLs.has(currentURL) && !isProcessing) {
    isProcessing = true;
    processedURLs.add(currentURL);
    
    // Extract MS_TOKEN whenever we capture a URL
    const msToken = extractMSToken();
    
    browser.runtime.sendMessage({
      type: 'TIKTOK_URL_FOUND',
      url: currentURL,
      msToken: msToken
    });
  }
}

// Send MS_TOKEN on page load/refresh
function sendMSToken() {
  const msToken = extractMSToken();
  if (msToken) {
    console.log('MS_TOKEN found:', msToken.substring(0, 20) + '...');
    browser.runtime.sendMessage({
      type: 'MS_TOKEN_FOUND',
      msToken: msToken
    }).then(response => {
      if (response && response.success) {
        showNotification('✓ MS_TOKEN updated in config');
      }
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
      // Also check for MS_TOKEN on navigation
      if (window.location.hostname.includes('tiktok.com')) {
        sendMSToken();
      }
    }, 1000);
  }
});

observer.observe(document.body, {
  childList: true,
  subtree: true
});

checkAndCaptureURL();

// Send MS_TOKEN on initial load and page changes
if (window.location.hostname.includes('tiktok.com')) {
  console.log('TikTok page detected, will send MS_TOKEN...');
  // Wait a bit for cookies to be available
  setTimeout(() => {
    console.log('Attempting to send MS_TOKEN...');
    sendMSToken();
  }, 2000);
  
  // Also send MS_TOKEN periodically in case it updates
  setInterval(sendMSToken, 60000); // Every 60 seconds
}