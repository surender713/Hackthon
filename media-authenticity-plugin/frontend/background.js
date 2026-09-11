chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "verify-authenticity",
    title: "Verify with Authenticity Plugin",
    contexts: ["selection"],
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== "verify-authenticity" || !tab?.id) {
    return;
  }

  const selectedText = (info.selectionText || "").trim();
  if (!selectedText) {
    return;
  }

  try {
    await chrome.tabs.sendMessage(tab.id, {
      type: "VERIFY_TEXT",
      text: selectedText,
    });
  } catch {
    // Content script may not be injected yet (e.g. chrome:// pages or fresh tab).
    await chrome.scripting.insertCSS({
      target: { tabId: tab.id },
      files: ["styles.css"],
    });
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ["content.js"],
    });
    await chrome.tabs.sendMessage(tab.id, {
      type: "VERIFY_TEXT",
      text: selectedText,
    });
  }
});
