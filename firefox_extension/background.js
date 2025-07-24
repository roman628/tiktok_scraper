browser.runtime.onMessage.addListener((message, sender) => {
  if (message.type === 'TIKTOK_URL_FOUND') {
    const url = message.url;
    const isManual = message.source === 'manual';
    
    fetch('http://localhost:8765/add_url', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ url: url })
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
      
      if (sender.tab) {
        browser.tabs.sendMessage(sender.tab.id, {
          type: 'URL_ADDED_ERROR',
          url: url,
          error: error.message || 'Connection failed. Make sure the URL server is running.'
        }).catch(() => {});
      }
      
      if (isManual) {
        browser.runtime.sendMessage({
          type: 'MANUAL_ADD_ERROR',
          error: error.message || 'Connection failed. Make sure the URL server is running.'
        }).catch(() => {});
      }
    });
  }
});

browser.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab.url && tab.url.includes('tiktok.com')) {
    browser.tabs.sendMessage(tabId, {
      type: 'CHECK_TIKTOK_URL'
    }).catch(() => {
    });
  }
});