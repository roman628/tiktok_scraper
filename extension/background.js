// Default server configuration - now pointing to Django server
const DEFAULT_CONFIG = {
  serverUrl: 'http://localhost',
  serverPort: '8000'  // Django default port
};

// Get server configuration from storage
async function getServerConfig() {
  try {
    const result = await browser.storage.local.get(['serverUrl', 'serverPort']);
    return {
      serverUrl: result.serverUrl || DEFAULT_CONFIG.serverUrl,
      serverPort: result.serverPort || DEFAULT_CONFIG.serverPort
    };
  } catch (error) {
    console.error('Error getting server config:', error);
    return DEFAULT_CONFIG;
  }
}

// Build the full server URL for Django API
function buildServerUrl(config) {
  return `${config.serverUrl}:${config.serverPort}/api/submit-url/`;
}

// Handle messages from content script and popup
browser.runtime.onMessage.addListener(async (message, sender) => {
  if (message.type === 'MS_TOKEN_FOUND') {
    // Update MS_TOKEN in config.toml
    const config = await getServerConfig();
    const updateEndpoint = `${config.serverUrl}:${config.serverPort}/api/update-token/`;
    
    console.log('Sending MS_TOKEN to server...');
    
    return fetch(updateEndpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ ms_token: message.msToken })
    }).then(response => response.json())
    .then(data => {
      console.log('MS_TOKEN updated successfully:', data);
      
      // Send notification back to content script
      if (sender.tab) {
        browser.tabs.sendMessage(sender.tab.id, {
          type: 'MS_TOKEN_UPDATE_SUCCESS',
          message: data.message
        }).catch(() => {});
      }
      
      return { success: true, message: data.message };
    }).catch(error => {
      console.error('Error updating MS_TOKEN:', error);
      
      // Send error notification back to content script  
      if (sender.tab) {
        browser.tabs.sendMessage(sender.tab.id, {
          type: 'MS_TOKEN_UPDATE_ERROR',
          error: error.message
        }).catch(() => {});
      }
      
      return { success: false, error: error.message };
    });
  } else if (message.type === 'TIKTOK_URL_FOUND') {
    const url = message.url;
    const isManual = message.source === 'manual';
    
    // Get current server configuration
    const config = await getServerConfig();
    const serverEndpoint = buildServerUrl(config);
    
    // Include MS_TOKEN if available
    const requestBody = { url: url };
    if (message.msToken) {
      requestBody.ms_token = message.msToken;
    }
    
    fetch(serverEndpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody)
    }).then(response => response.json())
    .then(data => {
      console.log('URL added successfully:', data);
      
      if (sender.tab) {
        browser.tabs.sendMessage(sender.tab.id, {
          type: 'URL_ADDED_SUCCESS',
          url: url,
          message: data.message
        }).catch(() => {});
      }
      
      if (isManual) {
        browser.runtime.sendMessage({
          type: 'MANUAL_ADD_SUCCESS',
          url: url
        }).catch(() => {});
      }
    }).catch(error => {
      console.error('Error adding URL:', error);
      const errorMessage = `Connection failed to ${serverEndpoint}. Make sure the URL server is running.`;
      
      if (sender.tab) {
        browser.tabs.sendMessage(sender.tab.id, {
          type: 'URL_ADDED_ERROR',
          url: url,
          error: errorMessage
        }).catch(() => {});
      }
      
      if (isManual) {
        browser.runtime.sendMessage({
          type: 'MANUAL_ADD_ERROR',
          error: errorMessage
        }).catch(() => {});
      }
    });
  } else if (message.type === 'GET_SERVER_CONFIG') {
    // Return current server configuration
    return getServerConfig();
  } else if (message.type === 'UPDATE_SERVER_CONFIG') {
    // Update server configuration
    try {
      await browser.storage.local.set({
        serverUrl: message.serverUrl,
        serverPort: message.serverPort
      });
      return { success: true };
    } catch (error) {
      console.error('Error updating server config:', error);
      return { success: false, error: error.message };
    }
  }
});

// Check TikTok tabs when they complete loading
browser.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab.url && tab.url.includes('tiktok.com')) {
    browser.tabs.sendMessage(tabId, {
      type: 'CHECK_TIKTOK_URL'
    }).catch(() => {});
  }
});

// Initialize storage with default values if not set
browser.runtime.onInstalled.addListener(async () => {
  const config = await browser.storage.local.get(['serverUrl', 'serverPort']);
  if (!config.serverUrl || !config.serverPort) {
    await browser.storage.local.set(DEFAULT_CONFIG);
  }
});