function isTikTokVideoURL(url) {
  const tiktokVideoPattern = /^https:\/\/www\.tiktok\.com\/@[^\/]+\/video\/\d+/;
  return tiktokVideoPattern.test(url);
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
    
    browser.runtime.sendMessage({
      type: 'TIKTOK_URL_FOUND',
      url: currentURL
    });
  }
}

browser.runtime.onMessage.addListener((message) => {
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
  }
});

let lastURL = window.location.href;
const observer = new MutationObserver(() => {
  if (window.location.href !== lastURL) {
    lastURL = window.location.href;
    setTimeout(checkAndCaptureURL, 1000);
  }
});

observer.observe(document.body, {
  childList: true,
  subtree: true
});

checkAndCaptureURL();