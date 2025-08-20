function isTikTokVideoURL(url) {
  const tiktokVideoPattern = /^https:\/\/www\.tiktok\.com\/@[^\/]+\/video\/\d+/;
  return tiktokVideoPattern.test(url);
}

function updateStatus(message, type = 'info') {
  const statusEl = document.getElementById('status');
  statusEl.textContent = message;
  statusEl.className = `status ${type}`;
}

function updateCurrentURL(url) {
  const urlEl = document.getElementById('currentUrl');
  if (url) {
    urlEl.textContent = url;
    urlEl.style.display = 'block';
  } else {
    urlEl.style.display = 'none';
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const manualButton = document.getElementById('manualCapture');
  
  browser.runtime.onMessage.addListener((message) => {
    if (message.type === 'MANUAL_ADD_SUCCESS') {
      updateStatus('✓ URL added successfully', 'success');
      manualButton.textContent = 'Added!';
      setTimeout(() => window.close(), 1000);
    } else if (message.type === 'MANUAL_ADD_ERROR') {
      updateStatus('✗ Error: ' + message.error, 'error');
      manualButton.disabled = false;
      manualButton.textContent = 'Retry';
    }
  });
  
  browser.tabs.query({ active: true, currentWindow: true }).then(tabs => {
    const currentTab = tabs[0];
    const url = currentTab.url;
    
    updateCurrentURL(url);
    
    if (url && url.includes('tiktok.com')) {
      if (isTikTokVideoURL(url)) {
        updateStatus('✓ TikTok video detected', 'success');
        manualButton.disabled = false;
        manualButton.textContent = 'Add This URL';
      } else {
        updateStatus('TikTok page detected, but not a video', 'info');
        manualButton.disabled = true;
      }
    } else {
      updateStatus('Not on TikTok', 'error');
      manualButton.disabled = true;
    }
  });
  
  manualButton.addEventListener('click', () => {
    browser.tabs.query({ active: true, currentWindow: true }).then(tabs => {
      const currentTab = tabs[0];
      const url = currentTab.url;
      
      if (isTikTokVideoURL(url)) {
        manualButton.disabled = true;
        manualButton.textContent = 'Adding...';
        updateStatus('Adding URL...', 'info');
        
        browser.runtime.sendMessage({
          type: 'TIKTOK_URL_FOUND',
          url: url,
          source: 'manual'
        });
      }
    });
  });
});