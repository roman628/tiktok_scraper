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

function updateServerStatus(serverUrl, serverPort) {
  const serverStatusEl = document.getElementById('currentServer');
  serverStatusEl.textContent = `${serverUrl}:${serverPort}`;
}

async function loadServerSettings() {
  const config = await browser.runtime.sendMessage({ type: 'GET_SERVER_CONFIG' });
  document.getElementById('serverUrl').value = config.serverUrl;
  document.getElementById('serverPort').value = config.serverPort;
  updateServerStatus(config.serverUrl, config.serverPort);
}

async function saveServerSettings() {
  const serverUrl = document.getElementById('serverUrl').value.trim();
  const serverPort = document.getElementById('serverPort').value.trim();
  
  if (!serverUrl || !serverPort) {
    updateStatus('✗ Please fill in both server URL and port', 'error');
    return;
  }
  
  const result = await browser.runtime.sendMessage({
    type: 'UPDATE_SERVER_CONFIG',
    serverUrl: serverUrl,
    serverPort: serverPort
  });
  
  if (result.success) {
    updateStatus('✓ Settings saved successfully', 'success');
    updateServerStatus(serverUrl, serverPort);
  } else {
    updateStatus('✗ Failed to save settings', 'error');
  }
}

async function testConnection() {
  const serverUrl = document.getElementById('serverUrl').value.trim();
  const serverPort = document.getElementById('serverPort').value.trim();
  
  if (!serverUrl || !serverPort) {
    updateStatus('✗ Please fill in server settings first', 'error');
    return;
  }
  
  const testButton = document.getElementById('testConnection');
  testButton.disabled = true;
  testButton.textContent = 'Testing...';
  
  try {
    const response = await fetch(`${serverUrl}:${serverPort}/add_url`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ url: 'test', test: true })
    });
    
    if (response.ok) {
      updateStatus('✓ Connection successful!', 'success');
      document.getElementById('serverStatus').className = 'server-status connected';
    } else {
      throw new Error('Server responded with error');
    }
  } catch (error) {
    updateStatus(`✗ Connection failed: ${error.message}`, 'error');
    document.getElementById('serverStatus').className = 'server-status disconnected';
  } finally {
    testButton.disabled = false;
    testButton.textContent = 'Test Connection';
  }
}

// Function to check MS_TOKEN status
async function checkMSTokenStatus() {
  const tokenStatusDiv = document.getElementById('tokenStatus');
  const tokenIndicator = document.getElementById('tokenIndicator');
  const tokenMessage = document.getElementById('tokenMessage');
  
  // Check if we're on TikTok
  const tabs = await browser.tabs.query({ active: true, currentWindow: true });
  const currentTab = tabs[0];
  
  if (currentTab.url && currentTab.url.includes('tiktok.com')) {
    tokenStatusDiv.style.display = 'block';
    
    // Request MS_TOKEN from content script
    try {
      const response = await browser.tabs.sendMessage(currentTab.id, { type: 'GET_MS_TOKEN' });
      if (response && response.msToken) {
        tokenIndicator.textContent = 'FOUND';
        tokenIndicator.style.background = '#2ed573';
        tokenIndicator.style.color = 'white';
        tokenMessage.textContent = '✓ MS_TOKEN detected';
      } else {
        tokenIndicator.textContent = 'NOT FOUND';
        tokenIndicator.style.background = '#ff4757';
        tokenIndicator.style.color = 'white';
        tokenMessage.textContent = '⚠️ MS_TOKEN not found';
      }
    } catch (e) {
      // Content script might not be injected yet
      tokenIndicator.textContent = 'CHECKING';
      tokenIndicator.style.background = '#ffa502';
      tokenIndicator.style.color = 'white';
      tokenMessage.textContent = 'Checking for MS_TOKEN...';
    }
  } else {
    tokenStatusDiv.style.display = 'none';
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const manualButton = document.getElementById('manualCapture');
  const settingsToggle = document.getElementById('settingsToggle');
  const settingsContent = document.getElementById('settingsContent');
  const toggleIcon = document.getElementById('toggleIcon');
  const saveButton = document.getElementById('saveSettings');
  const testButton = document.getElementById('testConnection');
  
  // Load server settings on startup
  loadServerSettings();
  
  // Handle settings toggle
  settingsToggle.addEventListener('click', () => {
    settingsContent.classList.toggle('show');
    toggleIcon.classList.toggle('expanded');
  });
  
  // Handle save settings
  saveButton.addEventListener('click', saveServerSettings);
  
  // Handle test connection
  testButton.addEventListener('click', testConnection);
  
  // Handle messages from background script
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
  
  // Check current tab
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
      // Check MS_TOKEN status when on TikTok
      checkMSTokenStatus();
    } else {
      updateStatus('Not on TikTok', 'error');
      manualButton.disabled = true;
    }
  });
  
  // Handle manual capture
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