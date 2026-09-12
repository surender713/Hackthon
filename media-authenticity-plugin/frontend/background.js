chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "verify-authenticity",
    title: "Verify with Authenticity Plugin",
    contexts: ["selection", "image"],
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== "verify-authenticity" || !tab?.id) {
    return;
  }

  const message = info.mediaType === "image"
    ? { type: "VERIFY_IMAGE", action: "analyzeImage", srcUrl: info.srcUrl }
    : { type: "VERIFY_TEXT", text: (info.selectionText || "").trim() };

  if (message.type === "VERIFY_IMAGE" && !message.srcUrl) return;
  if (message.type === "VERIFY_TEXT" && !message.text) return;

  try {
    await chrome.tabs.sendMessage(tab.id, message);
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
    await chrome.tabs.sendMessage(tab.id, message);
  }
});
